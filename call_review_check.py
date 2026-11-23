"""Check company reviews for orders created in a selected period and mark verified matches."""
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import date
from flask import jsonify, request
from negative_reviews import get_client, normalize_name, normalize_order, parse_date
from negative_reviews import Shop
from call_review_analytics import (_orders, _shops, _reviews, SHOP_ALIASES,
    BORNIATCO_COMPANY_ID, TOYVO_COMPANY_ID, BOTREBA_COMPANY_ID, SVIY_COMPANY_ID,
    TABS, CALL_BOOK)

_lock=threading.Lock()
_state={"status":"idle","message":"Готово до перевірки."}
FALLBACK={"borniatco":("Borniatco",BORNIATCO_COMPANY_ID),
          "toyvo - дроп":("ToyVo",TOYVO_COMPANY_ID),
          "botreba -дроп":("BoTreba",BOTREBA_COMPANY_ID),
          "свій":("Свій інтернет магазин",SVIY_COMPANY_ID)}

def _worker(start,end,login_map,run_id):
    global _state
    try:
        orders,stats,_=_orders(start,end)
        directory=_shops()
        shops=sorted({shop for shop,_ in orders})
        found_by_shop={}
        errors=[]
        unknown=[]
        for index,name in enumerate(shops,1):
            _state={"status":"running","run_id":run_id,
                    "message":f"Prom: магазин {index}/{len(shops)}"}
            info=directory.get(SHOP_ALIASES.get(name,name))
            if not info and name in FALLBACK:
                label,company_id=FALLBACK[name]
                info=Shop(label,company_id)
            if not info or not login_map.get(info.id):
                unknown.append(name)
                continue
            for account in login_map[info.id]:
                try:
                    for attempt in range(3):
                        try:
                            # All historical reviews through today, not just the 30-day window.
                            matched,_,_=_reviews(info,account,start,date.today())
                            found_by_shop[name]=matched
                            break
                        except Exception as exc:
                            print("[review-check] shop=%s attempt=%d error=%s" %
                                  (name,attempt+1,type(exc).__name__),flush=True)
                            if attempt==2:raise
                            time.sleep(1.5*(attempt+1))
                    break
                except Exception:
                    continue
            if name not in found_by_shop:errors.append(name)

        # Do not write anything if no store returned a reliable review list.
        if not found_by_shop:
            _state={"status":"partial","run_id":run_id,"message":"Жоден магазин не перевірено — записів немає.",
                    "total_orders":stats["selected"],"written":0,"already_marked":0,
                    "matched":0,"unverified":stats["selected"],"unavailable_shops":errors,
                    "unmapped_shops":unknown}
            return
        candidates=defaultdict(list)
        matched=already=0
        for (shop,_),entries in orders.items():
            reviews=found_by_shop.get(shop)
            if reviews is None:continue
            for item in entries:
                ids=[v for v in (item["order"],item["external_id"]) if v]
                if not any(reviews.get(v) for v in ids):continue
                matched+=1
                if item["label"]=="є відгук":
                    already+=1
                elif not item["label"] or item["label"]=="без мітки":
                    candidates[item["tab"]].append(item)
                # Preserve every manager-entered call status.
        book=get_client().open_by_key(CALL_BOOK)
        written=0
        skipped=0
        write_errors=[]
        # Recheck each row immediately before updating, to avoid stale row matches.
        for tab,items in candidates.items():
            sheet=book.worksheet(tab)
            for item in items:
                try:
                    row=item["row"]
                    current=sheet.get(f"C{row}:I{row}")
                    cells=(current[0] if current else [])+[""]*7
                    cells=cells[:7]
                    if (parse_date(str(cells[0])[:10])!=item["created"] or
                        normalize_name(cells[1])!=item["shop"] or
                        normalize_order(cells[4])!=item["external_id"] or
                        normalize_order(cells[5])!=item["order"]):
                        skipped+=1
                        continue
                    # Only empty cells are eligible. Never overwrite a manager's label,
                    # including a label entered after the initial sheet read.
                    if str(cells[6]).strip():
                        skipped+=1
                        continue
                    sheet.update_acell(f"I{row}","є відгук")
                    written+=1
                except Exception as exc:
                    skipped+=1
                    if tab not in write_errors:write_errors.append(tab)
                    print("[review-check] write failure tab=%s type=%s" %
                          (tab,type(exc).__name__),flush=True)
        unverified=sum(len(entries) for (shop,_),entries in orders.items() if shop not in found_by_shop)
        _state={"status":"partial" if errors or unknown or skipped else "success",
                "run_id":run_id,"message":"Перевірку завершено. Оновлено лише підтверджені відгуки.",
                "total_orders":stats["selected"],"matched":matched,
                "already_marked":already,"written":written,"skipped":skipped,
                "unverified":unverified,"unavailable_shops":errors,
                "unmapped_shops":unknown,"write_error_tabs":write_errors,
                "excluded_shop_rows":stats["excluded_shop_rows"]}
    except Exception as exc:
        _state={"status":"error","run_id":run_id,"message":str(exc)[:300]}
    finally:
        _lock.release()

def register(app,login_map_fn):
    @app.route("/call-reviews/check/start",methods=["POST"])
    def call_reviews_check_start():
        global _state
        body=request.get_json(silent=True) or {}
        start=parse_date(body.get("since"))
        end=parse_date(body.get("until"))
        if not start or not end or start>end or end>date.today():
            return jsonify({"error":"Виберіть коректний період дат створення замовлень."}),400
        if (end-start).days>90:
            return jsonify({"error":"Максимальний діапазон — 90 днів."}),400
        if not _lock.acquire(False):
            return jsonify({"error":"Перевірка вже виконується."}),409
        run_id=uuid.uuid4().hex
        _state={"status":"running","run_id":run_id,"message":"Збираємо замовлення за датою створення…"}
        try:
            mapping=login_map_fn()
            threading.Thread(target=_worker,args=(start,end,mapping,run_id),daemon=True).start()
        except Exception:
            _lock.release()
            raise
        return jsonify({"status":"started","run_id":run_id})

    @app.route("/call-reviews/check/status",methods=["GET"])
    def call_reviews_check_status():
        return jsonify(_state)
