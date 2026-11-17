"""Product-on-company-site reviews: isolated, duplicate-safe Prom export."""
from datetime import datetime
from zoneinfo import ZoneInfo

from negative_reviews import get_client, load_active_shops, parse_date, normalize_name
from negative_review_api import _switch, _read, _order_id

SOURCE_BOOK = "1B8aq-wNhaCoDAGm_nbOu36GNQp8y0ovAkYoO7pjvxMA"
SOURCE_TAB = "Про товари на сайті компанії"
TARGET_BOOK = "1lN_YfDY8sg4MRbTw8Griy_TVsNehzrgt6YzOy_K7SYc"
URL = "https://my.prom.ua/cms/opinions/product/site/context"


def _extract(opinion, shop, day):
    if not isinstance(opinion, dict):
        raise ValueError("Некоректна картка відгуку")
    if str(opinion.get("companyId")) != str(shop.id):
        raise ValueError("Prom повернув відгук іншого магазину")
    date_text = str(opinion.get("dateCreated") or "")[:10]
    date = parse_date(date_text)
    if not date:
        raise ValueError("Відгук без коректної дати")
    rating = opinion.get("rating")
    if type(rating) is not int or rating not in (1, 2, 3, 4, 5):
        raise ValueError("Відгук без коректного рейтингу")
    review_id = str(opinion.get("id") or "")
    if not review_id.isdigit():
        raise ValueError("Відгук без ID")
    if date != day:
        return None, date
    order = _order_id(opinion)
    if not order:
        raise ValueError("Відгук за вибрану дату без ID замовлення Prom")
    text = "\n".join(str(opinion[k]).strip() for k in ("title", "text", "pros", "cons")
                     if isinstance(opinion.get(k), str) and opinion[k].strip())
    return {"order": order, "date": date.strftime("%d.%m"),
            "shop": shop.name, "text": text, "rating": rating,
            "review_id": review_id}, date


def _collect(shop, account, day):
    opener, _ = _switch(account)
    result = []
    seen = set()
    previous = None
    ordered = True
    for page in range(1, 201):
        url = URL + "?page=%d&perPage=20&sortingQuery=-date_created&pageType=site" % page
        data = _read(opener, url)
        context = data.get("context")
        if not isinstance(context, dict):
            raise ValueError("Prom не повернув context для відгуків про товари на сайті")
        opinions = context.get("opinions")
        pagination = context.get("pagination")
        if not isinstance(opinions, list) or not isinstance(pagination, dict):
            raise ValueError("Некоректна структура сторінки відгуків")
        if not opinions:
            return result
        dates = []
        for opinion in opinions:
            item, date = _extract(opinion, shop, day)
            rid = str(opinion["id"])
            if rid in seen:
                raise ValueError("Prom повторив відгук на різних сторінках")
            seen.add(rid)
            dates.append(date)
            if previous is not None and date > previous:
                ordered = False
            previous = date
            if item:
                result.append(item)
        try:
            pages = int(pagination.get("num_pages") or 1)
        except (TypeError, ValueError):
            raise ValueError("Некоректна пагінація Prom")
        if page >= pages or (ordered and dates and max(dates) < day):
            return result
    raise ValueError("Перевищено ліміт 200 сторінок Prom")


def _write(book, tab, reviews):
    if not reviews:
        return 0
    sheet = book.worksheet(tab)
    rows = sheet.get("D:I")
    existing = {}
    last = 2

    def day_month(value):
        value = str(value or "").strip()
        parsed = parse_date(value)
        if parsed:
            return parsed.strftime("%d.%m")
        import re
        match = re.match(r"^(\d{1,2})\.(\d{1,2})(?:\.|$)", value)
        return f"{int(match.group(1)):02d}.{int(match.group(2)):02d}" if match else ""

    def clean_text(value):
        import re
        return re.sub(r"^⭐\\s*[1-5]/5\\s*\\n?", "", str(value or "").strip()).strip()

    for index, row in enumerate(rows, 1):
        padded = row + [""] * (6 - len(row))
        order, date, shop, text = padded[0], padded[3], padded[4], padded[5]
        if any(str(v).strip() for v in (order, date, shop, text)):
            last = max(last, index)
        normalized_date = day_month(date)
        if normalized_date:
            key = (str(order).strip(), normalized_date,
                   normalize_name(shop), clean_text(text))
            existing.setdefault(key, index)

    fresh = []
    updates = []
    link_rows = []
    seen = set()
    for item in reviews:
        key = (item["order"], item["date"], normalize_name(item["shop"]),
               clean_text(item["text"]))
        if key in seen:
            continue
        seen.add(key)
        if key in existing:
            row_number = existing[key]
            # Update formatting of previously exported reviews, without
            # adding duplicate rows or touching any manager work columns.
            previous = rows[row_number - 1] if row_number <= len(rows) else []
            previous_text = previous[5] if len(previous) > 5 else ""
            display_text = f"⭐ {item['rating']}/5" + (
                chr(10) + item["text"] if item["text"] else "")
            if previous_text != display_text:
                updates.append({"range": f"'{tab}'!I{row_number}",
                                "values": [[display_text]]})
            existing_date = previous[3] if len(previous) > 3 else ""
            if str(existing_date).strip() != item["date"]:
                updates.append({"range": f"'{tab}'!G{row_number}",
                                "values": [[item["date"]]]})
            link_rows.append((row_number, item["order"]))
        else:
            fresh.append(item)

    first = last + 1
    if fresh and sheet.row_count < first + len(fresh) - 1:
        sheet.add_rows(first + len(fresh) - 1 - sheet.row_count)

    for offset, item in enumerate(fresh):
        row = first + offset
        body = f"⭐ {item['rating']}/5" + (
            chr(10) + item["text"] if item["text"] else "")
        for col, value in (("D", item["order"]), ("G", item["date"]),
                           ("H", item["shop"]), ("I", body)):
            updates.append({"range": f"'{tab}'!{col}{row}", "values": [[value]]})
        link_rows.append((row, item["order"]))

    if updates:
        book.values_batch_update({"valueInputOption": "RAW", "data": updates})
    if link_rows:
        requests = []
        for row, _order in link_rows:
            requests.append({"repeatCell": {
                "range": {"sheetId": sheet.id, "startRowIndex": row - 1,
                          "endRowIndex": row, "startColumnIndex": 8,
                          "endColumnIndex": 9},
                "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP",
                                              "verticalAlignment": "TOP"}},
                "fields": "userEnteredFormat.wrapStrategy,userEnteredFormat.verticalAlignment"
            }})
        for row, order in link_rows:
            if not str(order).isdigit():
                continue
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet.id, "startRowIndex": row - 1,
                              "endRowIndex": row, "startColumnIndex": 3,
                              "endColumnIndex": 4},
                    "cell": {"userEnteredFormat": {"textFormat": {
                        "link": {"uri": "https://my.prom.ua/cms/order/edit/" + str(order)}
                    }}},
                    "fields": "userEnteredFormat.textFormat.link",
                }
            })
        if requests:
            book.batch_update({"requests": requests})
    return len(fresh)


def export_product_site_reviews(date_text, login_map, progress=None):
    day = parse_date(date_text)
    if not day:
        raise ValueError("Некоректна дата")
    if not login_map:
        raise RuntimeError("Немає підтвердженої карти sign-to магазинів")
    shops = load_active_shops(SOURCE_BOOK, SOURCE_TAB)
    if not shops:
        raise RuntimeError("На аркуші «Про товари на сайті компанії» немає активних магазинів")
    book = get_client().open_by_key(TARGET_BOOK)
    # Resolve destination tabs before making any writes.
    book.worksheet("Негативні")
    book.worksheet("Позитивні")
    collected = {"Негативні": [], "Позитивні": []}
    errors = []
    for i, shop in enumerate(shops, 1):
        if progress:
            progress(i, len(shops), shop.name)
        accounts = login_map.get(str(shop.id)) or []
        if not accounts:
            errors.append(shop.name + ": відсутній sign-to ID")
            continue
        result = None
        for account in accounts:
            try:
                result = _collect(shop, account, day)
                break
            except Exception as exc:
                print("[product-site-reviews] shop=%s error=%s" % (shop.name, type(exc).__name__), flush=True)
        if result is None:
            errors.append(shop.name + ": не вдалося перевірити відгуки")
            continue
        for item in result:
            collected["Негативні" if item["rating"] <= 3 else "Позитивні"].append(item)
    if errors:
        # Do not report zero as a clean result if any shop was missed.
        raise RuntimeError("Неповна перевірка магазинів: " + "; ".join(errors[:5]))
    written = {tab: _write(book, tab, items) for tab, items in collected.items()}
    return {"checked_shops": len(shops),
            "collected_negative": len(collected["Негативні"]),
            "collected_positive": len(collected["Позитивні"]),
            "written_negative": written["Негативні"],
            "written_positive": written["Позитивні"],
            "written": sum(written.values())}
