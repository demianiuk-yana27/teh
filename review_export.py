import os
import re
import time
from datetime import datetime

from selenium.webdriver.common.by import By

from negative_reviews import COMPANY_REVIEWS_URL, PRODUCT_REVIEWS_URL, PromBrowser, get_client, load_active_shops, normalize_name, parse_date


REVIEW_URLS = {
    "company": COMPANY_REVIEWS_URL,
    "product": PRODUCT_REVIEWS_URL,
}


def _date_number(value):
    parsed = parse_date(value)
    return parsed.toordinal() if parsed else 0


def _sheet_name(book, review_type):
    env_name = os.environ.get("PROM_COMPANY_REVIEWS_SHEET" if review_type == "company" else "PROM_PRODUCT_REVIEWS_SHEET", "").strip()
    if env_name:
        book.worksheet(env_name)
        return env_name

    titles = [ws.title for ws in book.worksheets()]
    blocked = ("аналітик", "показник", "список магазин", "замовлен")
    if review_type == "company":
        preferred = ["Відгуки про компанію", "Відгуки компанії", "Компанія"]
        keywords = ("компан",)
    else:
        preferred = ["Відгуки про товари", "Відгуки товарів", "Товари"]
        keywords = ("товар", "продукт")

    by_norm = {normalize_name(title): title for title in titles}
    for candidate in preferred:
        if normalize_name(candidate) in by_norm:
            return by_norm[normalize_name(candidate)]
    for title in titles:
        low = normalize_name(title)
        if "відгу" in low and any(key in low for key in keywords) and not any(key in low for key in blocked):
            return title
    raise RuntimeError(
        f"Не вдалося визначити аркуш для {'відгуків про компанію' if review_type == 'company' else 'відгуків про товари'}. "
        "За потреби задайте PROM_COMPANY_REVIEWS_SHEET / PROM_PRODUCT_REVIEWS_SHEET у Render."
    )


def _existing_keys(sheet, dates):
    keys = set()
    for row in sheet.get("A:Y")[2:]:
        padded = row + [""] * (25 - len(row))
        date_value = parse_date(padded[6])
        shop = str(padded[7]).strip()
        order = re.search(r"\d+", str(padded[3] or ""))
        if date_value and shop and order:
            date_text = date_value.strftime("%d.%m.%Y")
            if date_text in dates:
                keys.add((date_text, normalize_name(shop), order.group(0)))
    return keys


def _extract_candidates(driver, review_type):
    if review_type == "company":
        script = r'''
        const rows = Array.from(document.querySelectorAll('[data-qaid="opinion_row"]'));
        return rows.map(row => {
          const order = row.querySelector('[data-qaid="order"]');
          const dateEl = row.querySelector('[data-qaid="date_created"]');
          const legacy = row.querySelector('[data-qaid="rating_bar"] .b-rating__bg');
          const svg = row.querySelector('[data-qaid="opinion_rating"]');
          const comment = row.querySelector('[data-qaid="opinion_comment"]');
          const orderId = ((order?.textContent || '').match(/№\s*(\d+)/) || [])[1] || ((order?.getAttribute('href') || '').match(/\/order\/edit\/(\d+)/) || [])[1];
          const dm = (dateEl?.innerText || '').match(/(\d{1,2})\.(\d{1,2})\.(\d{2})(?!\d)/);
          const legacyPct = parseFloat(legacy?.style?.width || '0');
          const svgPct = Math.max(0, ...Array.from(svg?.querySelectorAll('stop[offset]') || []).map(x => parseFloat(x.getAttribute('offset') || '0')).filter(Number.isFinite));
          const pct = legacyPct || svgPct;
          if (!orderId || !dm || !pct) return null;
          const year = 2000 + Number(dm[3]);
          const date = dm[1].padStart(2,'0') + '.' + dm[2].padStart(2,'0') + '.' + year;
          const tags = Array.from(row.querySelectorAll('[data-qaid="edited_tags_item"]')).map(x => (x.textContent || '').trim()).filter(Boolean);
          const text = [(comment?.textContent || '').trim(), ...tags].filter(Boolean).join('\n');
          return {orderId, date, rating: Math.max(1, Math.min(5, Math.round(pct / 20))), text};
        }).filter(Boolean);
        '''
    else:
        script = r'''
        const rows = Array.from(document.querySelectorAll('[data-qaid="opinion_item"]'));
        return rows.map(row => {
          const order = row.querySelector('[data-qaid="order"]');
          const dateEl = row.querySelector('[data-qaid="date"]');
          const ratingEl = row.querySelector('[data-qaid="rating"]');
          const title = row.querySelector('[data-qaid="opinion_title"]');
          const orderId = ((order?.getAttribute('href') || '').match(/\/order\/edit\/(\d+)/) || [])[1] || ((order?.textContent || '').match(/№\s*(\d+)/) || [])[1];
          const dm = (dateEl?.innerText || '').match(/(\d{1,2})\.(\d{1,2})\.(\d{2})(?!\d)/);
          const rating = Number(ratingEl?.getAttribute('data-rating') || 0);
          if (!orderId || !dm || !rating) return null;
          const year = 2000 + Number(dm[3]);
          const date = dm[1].padStart(2,'0') + '.' + dm[2].padStart(2,'0') + '.' + year;
          const titleText = (title?.textContent || '').trim();
          const text = titleText;
          return {orderId, date, rating: Math.max(1, Math.min(5, rating)), text};
        }).filter(Boolean);
        '''
    return driver.execute_script(script) or []


def _wait_reviews(driver, review_type, timeout=30):
    selector = '[data-qaid="opinion_row"]' if review_type == "company" else '[data-qaid="opinion_item"]'
    deadline = time.time() + timeout
    while time.time() < deadline:
        if driver.find_elements(By.CSS_SELECTOR, selector):
            return
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "немає відгуків" in body or "відгуків ще немає" in body or "нет отзывов" in body:
            return
        if "щось пішло не так" in body or "что-то пошло не так" in body:
            driver.refresh()
        time.sleep(0.5)
    raise RuntimeError(f"Prom не завантажив сторінку відгуків ({review_type}).")


def _collect(browser, review_type, shop, since, until):
    driver = browser.driver
    since_num = _date_number(since)
    until_num = _date_number(until) if until else None
    collected = {}
    seen = set()

    for page in range(1, 201):
        url = REVIEW_URLS[review_type] + f"?page={page}" + ("&per_page=20" if review_type == "company" else "")
        driver.get(url)
        _wait_reviews(driver, review_type)
        candidates = _extract_candidates(driver, review_type)
        body = driver.find_element(By.TAG_NAME, "body").text
        mentions = len(re.findall(r"№\s*\d+", body))
        if mentions and not candidates:
            raise RuntimeError(f"Prom показує замовлення на сторінці {page}, але картки відгуків не розпізнані.")
        if not candidates:
            break
        fingerprint = ",".join(sorted(str(x.get("orderId", "")) for x in candidates))
        if fingerprint in seen:
            raise RuntimeError(f"Prom повторив сторінку відгуків {page}; зупинено для безпеки.")
        seen.add(fingerprint)

        dates = []
        for item in candidates:
            date_num = _date_number(item.get("date"))
            if date_num:
                dates.append(date_num)
            rating = int(item.get("rating") or 0)
            if rating < 1 or rating > 3 or date_num < since_num or (until_num and date_num > until_num):
                continue
            order_id = str(item.get("orderId") or "").strip()
            collected[order_id] = {
                "type": review_type,
                "orderId": order_id,
                "date": item["date"],
                "rating": rating,
                "text": str(item.get("text") or "").strip(),
                "shopName": shop.name,
                "shopUrl": shop.url,
                "editUrl": "",
            }
        if dates and min(dates) < since_num:
            break
    return list(collected.values())


def _last_data_row(values):
    last = 2
    for idx, row in enumerate(values[2:], start=3):
        padded = row + [""] * (12 - len(row))
        if any(str(padded[col]).strip() for col in (3, 6, 7, 8, 11)):
            last = idx
    return last


def _write_reviews(book, sheet_name, reviews):
    if not reviews:
        return 0
    sheet = book.worksheet(sheet_name)
    dates = {item["date"] for item in reviews}
    existing = _existing_keys(sheet, dates)
    fresh = [item for item in reviews if (item["date"], normalize_name(item["shopName"]), item["orderId"]) not in existing]
    if not fresh:
        return 0
    fresh.sort(key=lambda x: (_date_number(x["date"]), normalize_name(x["shopName"]), x["orderId"]))

    values = sheet.get("A:L")
    row = _last_data_row(values) + 1
    previous_date = None
    requests = []
    link_requests = []
    sheet_id = sheet.id

    for review in fresh:
        if previous_date and previous_date != review["date"]:
            sheet.format(f"A{row}:L{row}", {"backgroundColor": {"red": 1, "green": 0.9, "blue": 0.7}})
            row += 1
        text = f"⭐ {review['rating']}/5" + (f"\n{review['text']}" if review["text"] else "")
        requests.extend([
            {"range": f"'{sheet_name}'!D{row}", "values": [[review["orderId"]]]},
            {"range": f"'{sheet_name}'!G{row}", "values": [[review["date"]]]},
            {"range": f"'{sheet_name}'!H{row}", "values": [[review["shopName"]]]},
            {"range": f"'{sheet_name}'!I{row}", "values": [[text]]},
            {"range": f"'{sheet_name}'!L{row}", "values": [[review["editUrl"]]]},
        ])
        if review["type"] == "company" and review["shopUrl"]:
            requests.append({"range": f"'{sheet_name}'!Y{row}", "values": [[review["shopUrl"]]]})
        link_requests.append({
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": row - 1, "endRowIndex": row, "startColumnIndex": 3, "endColumnIndex": 4},
                "cell": {"userEnteredFormat": {"textFormat": {"link": {"uri": f"https://my.prom.ua/cms/order/edit/{review['orderId']}"}}}},
                "fields": "userEnteredFormat.textFormat.link",
            }
        })
        previous_date = review["date"]
        row += 1

    book.values_batch_update({"valueInputOption": "USER_ENTERED", "data": requests})
    if link_requests:
        book.batch_update({"requests": link_requests})
    return len(fresh)


def run_review_export(spreadsheet_id, since, until=""):
    if not parse_date(since):
        raise ValueError("Некоректна дата початку вигрузки відгуків.")
    if until and not parse_date(until):
        raise ValueError("Некоректна дата завершення вигрузки відгуків.")

    client = get_client()
    book = client.open_by_key(spreadsheet_id)
    sheet_names = {kind: _sheet_name(book, kind) for kind in REVIEW_URLS}
    shops = load_active_shops(spreadsheet_id)
    browser = PromBrowser()
    written = {"company": 0, "product": 0}
    collected_count = {"company": 0, "product": 0}
    skipped = 0
    incomplete = 0
    try:
        browser.open_cms()
        for shop in shops:
            try:
                browser.switch_shop(shop)
            except Exception as exc:
                skipped += 1
                print(f"[{shop.name}] Не вдалося перемкнути магазин: {exc}")
                continue
            for review_type in ("company", "product"):
                try:
                    reviews = _collect(browser, review_type, shop, since, until)
                    collected_count[review_type] += len(reviews)
                    written[review_type] += _write_reviews(book, sheet_names[review_type], reviews)
                except Exception as exc:
                    incomplete += 1
                    print(f"[{shop.name}] {review_type}: {exc}")
    finally:
        browser.close()

    return {
        "active": len(shops),
        "skipped": skipped,
        "incomplete": incomplete,
        "collected_company": collected_count["company"],
        "collected_product": collected_count["product"],
        "written_company": written["company"],
        "written_product": written["product"],
        "written": written["company"] + written["product"],
    }
