"""Read-only preview: match Prom company opinions to call-center orders."""
import threading
import uuid
from datetime import datetime
from flask import jsonify, request
from negative_reviews import get_client, normalize_name, normalize_order, parse_date, Shop
from negative_review_api import _switch, _read, _order_id

SHOP_BOOK = "1B8aq-wNhaCoDAGm_nbOu36GNQp8y0ovAkYoO7pjvxMA"
CALL_BOOK = "1Ci_AoA6PBtlglbY_CY4d16tRX-7rxZ8_1YbEFft_hGs"
TABS = ("Yellow/Laggi/Born/Bybka/TrendVibe", "Наші", "Нові", "Дроп")
_lock = threading.Lock()
_state = {"status": "idle", "message": "Готово до перевірки."}


def _shops():
    # Shop directory is arranged in four pairs of columns, not TRUE flags.
    rows = get_client().open_by_key(SHOP_BOOK).worksheet("Продзвін - відгуки").get("A:H")
    result = {}
    for row in rows[1:]:
        cells = (row + [""] * 8)[:8]
        for col in (0, 2, 4, 6):
            name = cells[col].strip()
            shop_id = normalize_order(cells[col + 1])
            if name and shop_id:
                result[normalize_name(name)] = Shop(name, shop_id)
    if not result:
        raise RuntimeError("Не знайдено магазинів у довіднику продзвону.")
    return result


def _orders():
    book = get_client().open_by_key(CALL_BOOK)
    orders = {}
    counts = {}
    for tab in TABS:
        sheet = book.worksheet(tab)
        values = sheet.get("D:I")
        count = 0
        for row_number, row in enumerate(values, 1):
            cells = (row + [""] * 6)[:6]
            shop, order, status = cells[0], normalize_order(cells[4]), cells[5]
            if not shop or not order:
                continue
            orders.setdefault((normalize_name(shop), order), []).append(
                (tab, row_number, status))
            count += 1
        counts[tab] = count
    return orders, counts


def _company_reviews(shop, account, start, end):
    opener, csrf = _switch(account)
    found = set()
    seen = set()
    previous = None
    ordered = True
    missing_ids = 0
    inspected = 0
    for page in range(1, 201):
        data = _read(opener, "https://my.prom.ua/cms/opinions/company/list",
                     {"filters": [], "page": page, "pageType": "portal",
                      "perPage": 20, "searchQuery": "",
                      "sortingQuery": "default"}, csrf)
        opinions = data.get("opinions")
        pagination = data.get("pagination")
        if not isinstance(opinions, list) or not isinstance(pagination, dict):
            raise RuntimeError("Prom повернув некоректний список відгуків про компанію.")
        if not opinions:
            return found, inspected, missing_ids
        dates = []
        for opinion in opinions:
            if not isinstance(opinion, dict) or str(opinion.get("company_id")) != shop.id:
                raise RuntimeError("Prom повернув відгук іншого магазину.")
            review_id = str(opinion.get("id") or "")
            if not review_id.isdigit() or review_id in seen:
                raise RuntimeError("Некоректний або повторний ID відгуку Prom.")
            seen.add(review_id)
            date = parse_date(str(opinion.get("date_created") or "")[:10])
            if not date:
                ordered = False
                continue
            dates.append(date)
            if previous is not None and date > previous:
                ordered = False
            previous = date
            if start <= date <= end:
                inspected += 1
                order = _order_id(opinion)
                if order:
                    found.add(order)
                else:
                    missing_ids += 1
        try:
            total_pages = int(pagination.get("num_pages") or 1)
        except (TypeError, ValueError):
            raise RuntimeError("Некоректна пагінація відгуків Prom.")
        if page >= total_pages or (ordered and dates and max(dates) < start):
            return found, inspected, missing_ids
    raise RuntimeError("Перевищено ліміт 200 сторінок Prom.")


def _worker(start, end, login_map, run_id):
    global _state
    try:
        shops = _shops()
        orders, counts = _orders()
        results = {tab: {"matches": 0, "already_marked": 0} for tab in TABS}
        reviewed = 0
        without_id = 0
        order_index = {}
        shop_index = {}
        for (shop_name, order_id), entries in orders.items():
            order_index.setdefault(order_id, set()).add(shop_name)
            shop_index[shop_name] = shop_index.get(shop_name, 0) + len(entries)
        diagnostics = {
            "prom_orders_matching_any_tab": 0,
            "prom_orders_matching_other_shop": 0,
            "prom_reviews_with_shop_name_in_table": 0,
            "prom_reviews_without_shop_name_in_table": 0,
            "unique_prom_orders_checked": 0,
            "unique_sheet_order_ids": len(order_index),
            "unique_sheet_shop_names": len(shop_index),
        }
        observed_orders = set()
        errors = []
        missing_mapping = []
        for index, shop in enumerate(shops.values(), 1):
            _state = {"status": "running", "run_id": run_id,
                      "message": f"Перевіряємо магазин {index}/{len(shops)}…"}
            accounts = login_map.get(shop.id) or []
            if not accounts:
                missing_mapping.append(shop.name)
                continue
            found = None
            for account in accounts:
                try:
                    found = _company_reviews(shop, account, start, end)
                    break
                except Exception as exc:
                    print("[call-review-preview] shop=%s failure=%s" % (
                        shop.name, type(exc).__name__), flush=True)
            if found is None:
                errors.append(shop.name)
                continue
            order_ids, inspected, missed = found
            reviewed += inspected
            without_id += missed
            normalized_shop = normalize_name(shop.name)
            if normalized_shop in shop_index:
                diagnostics["prom_reviews_with_shop_name_in_table"] += inspected
            else:
                diagnostics["prom_reviews_without_shop_name_in_table"] += inspected
            for order in order_ids:
                observed_orders.add(order)
                if order in order_index:
                    diagnostics["prom_orders_matching_any_tab"] += 1
                    if normalized_shop not in order_index[order]:
                        diagnostics["prom_orders_matching_other_shop"] += 1
                for tab, _row, status in orders.get((normalized_shop, order), []):
                    results[tab]["matches"] += 1
                    if normalize_name(status) == "є відгук":
                        results[tab]["already_marked"] += 1
        diagnostics["unique_prom_orders_checked"] = len(observed_orders)
        _state = {
            "status": "success" if not errors and not missing_mapping else "partial",
            "run_id": run_id, "read_only": True, "writes": False,
            "date_from": start.isoformat(), "date_to": end.isoformat(),
            "shops_total": len(shops), "shops_checked": len(shops)-len(errors)-len(missing_mapping),
            "orders_by_tab": counts, "reviews_in_period": reviewed,
            "reviews_without_order_id": without_id,
            "matches_by_tab": results,
            "match_diagnostics": diagnostics,
            "total_matches": sum(v["matches"] for v in results.values()),
            "unavailable_shops": errors, "unmapped_shops": missing_mapping,
            "message": "Попередній перегляд завершено. Дані таблиці не змінювалися."
        }
    except Exception as exc:
        _state = {"status": "error", "run_id": run_id,
                  "message": type(exc).__name__ + ": " + str(exc)[:240]}
    finally:
        _lock.release()


def register(app, login_map_fn):
    @app.route("/call-reviews/preview", methods=["POST"])
    def call_reviews_preview():
        global _state
        data = request.get_json(silent=True) or {}
        start = parse_date(data.get("since"))
        end = parse_date(data.get("until"))
        if not start or not end or start > end:
            return jsonify({"status": "error", "message": "Виберіть коректний період."}), 400
        if not _lock.acquire(blocking=False):
            return jsonify({"status": "busy", "message": "Перевірка вже триває."}), 409
        run_id = uuid.uuid4().hex
        _state = {"status": "running", "run_id": run_id,
                  "message": "Починаємо перевірку без запису."}
        threading.Thread(target=_worker, args=(start, end, login_map_fn(), run_id),
                         daemon=True).start()
        return jsonify({"status": "started", "run_id": run_id})

    @app.route("/call-reviews/preview/status", methods=["GET"])
    def call_reviews_preview_status():
        return jsonify(_state)
