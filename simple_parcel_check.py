"""Match simple parcel requests to call review rows without replacing statuses."""
import re
import threading
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from flask import jsonify, request
from negative_reviews import get_client
from call_review_preview import CALL_BOOK, TABS

SOURCE_BOOK = "1ucWZbLHjZPRXnl8yHrYXeRGtVs0omSKS3jJZC4ImRw8"
SOURCE_TAB = "Запит на просту"
LABEL = "проста посилка"
KYIV = ZoneInfo("Europe/Kyiv")
_lock = threading.Lock()
_state = {"status": "idle"}

def request_date(value):
    try:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return date(1899, 12, 30) + timedelta(days=int(value))
        s = str(value or "").strip()
        if re.fullmatch(r"\d{1,2}\.\d{1,2}(?:\.\d{4})?", s):
            parts = list(map(int, s.split(".")))
            return date(parts[2] if len(parts) == 3 else 2026, parts[1], parts[0])
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (dt.astimezone(KYIV) if dt.tzinfo else dt).date()
    except (ValueError, TypeError, OverflowError):
        return None

def order_id(value):
    s = str(value or "").strip()
    return s.split(".")[0] if re.fullmatch(r"\d+(?:\.0+)?", s) else ""

def _worker(selected, run_id):
    global _state
    stats = dict(unique_orders=0, matched=0, written=0, occupied=0,
                 unmatched=0, invalid_dates=0, skipped=0, errors=0)
    try:
        client = get_client()
        source = client.open_by_key(SOURCE_BOOK).worksheet(SOURCE_TAB)
        ids = set()
        for row in source.get("D2:F", value_render_option="UNFORMATTED_VALUE"):
            d, _, number = (list(row) + [""] * 3)[:3]
            number = order_id(number)
            if not number:
                continue
            parsed = request_date(d)
            if parsed is None:
                stats["invalid_dates"] += 1
            elif parsed == selected:
                ids.add(number)
        stats["unique_orders"] = len(ids)
        book = client.open_by_key(CALL_BOOK)
        found = set()
        candidates = []
        # Read every target tab before making any changes.
        for tab in TABS:
            sheet = book.worksheet(tab)
            for index, row in enumerate(sheet.get("H2:I", value_render_option="FORMULA"), 2):
                number, status = (list(row) + [""] * 2)[:2]
                number = order_id(number)
                if number not in ids:
                    continue
                found.add(number)
                stats["matched"] += 1
                if status != "":
                    stats["occupied"] += 1
                else:
                    candidates.append((sheet, index, number))
        stats["unmatched"] = len(ids - found)
        for sheet, index, number in candidates:
            try:
                current = sheet.get(f"H{index}:I{index}", value_render_option="FORMULA")
                actual, status = (list(current[0] if current else []) + [""] * 2)[:2]
                if order_id(actual) != number:
                    stats["skipped"] += 1
                elif status != "":
                    stats["occupied"] += 1
                else:
                    sheet.update_acell(f"I{index}", LABEL)
                    stats["written"] += 1
            except Exception:
                stats["errors"] += 1
        _state = dict(stats, run_id=run_id,
                      status="partial" if stats["errors"] or stats["skipped"] else "success",
                      message="Перевірку простих посилок завершено.")
    except Exception as exc:
        _state = dict(stats, run_id=run_id, status="error",
                      message="Помилка перевірки: " + type(exc).__name__)
    finally:
        _lock.release()

def register(app):
    @app.route("/call-reviews/simple-parcels/start", methods=["POST"])
    def simple_parcels_start():
        global _state
        try:
            selected = date.fromisoformat((request.get_json(silent=True) or {}).get("date", ""))
        except (ValueError, TypeError):
            return jsonify(error="Оберіть коректну дату."), 400
        if not _lock.acquire(False):
            return jsonify(error="Перевірка вже виконується."), 409
        run_id = uuid.uuid4().hex
        _state = dict(status="running", run_id=run_id, message="Зіставляємо замовлення…")
        try:
            threading.Thread(target=_worker, args=(selected, run_id), daemon=True).start()
        except Exception:
            _lock.release()
            raise
        return jsonify(status="started", run_id=run_id)

    @app.route("/call-reviews/simple-parcels/status", methods=["GET"])
    def simple_parcels_status():
        return jsonify(_state)
