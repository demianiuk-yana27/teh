"""Read-only review-edit follow-up report for negative-review managers."""
import re
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime
from flask import jsonify
from negative_reviews import get_client, normalize_name, load_active_shops, Shop
from negative_review_api import _switch, _read, _order_id

BOOK_ID="16BqyyMUyTNiQaibRVyd-qXzo_XdAzxCvURPfBtGoiJg"
TARGET="перевірити чи редагували"
_lock=threading.Lock()
_state={"status":"idle","message":"Готово до перевірки."}

def _rating(value):
    match=re.search(r"(?:⭐|★|☆)\s*([1-5])\s*/\s*5",str(value or ""))
    return int(match.group(1)) if match else None

def _rows():
    book=get_client().open_by_key(BOOK_ID)
    result=[]
    for sheet in book.worksheets():
        # Restrict to catalog tabs only, not analytics or shop lists.
        if not normalize_name(sheet.title).startswith("каталог пром"):continue
        for index,values in enumerate(sheet.get("A:L"),1):
            row=(values+[""]*12)[:12]
            if normalize_name(row[0])!=TARGET:continue
            original=_rating(row[8])
            order=re.search(r"\b\d{6,15}\b",str(row[3]))
            result.append({"tab":sheet.title,"row":index,"manager":str(row[1]).strip() or "Не призначено",
                           "shop":str(row[7]).strip(),"order_id":order.group(0) if order else "",
                           "original_rating":original,"review_text":str(row[8])[:220],
                           "link":str(row[11]).strip() if str(row[11]).strip().startswith("https://") else ""})
    return result

def _collect(shop,account,earliest):
    opener,csrf=_switch(account)
    found=defaultdict(list)
    for kind in ("company","product"):
        previous=None
        ordered=True
        seen=set()
        for page in range(1,201):
            if kind=="company":
                data=_read(opener,"https://my.prom.ua/cms/opinions/company/list",
                           {"filters":[],"page":page,"pageType":"portal","perPage":20,
                            "searchQuery":"","sortingQuery":"default"},csrf)
                opinions=data.get("opinions")
                pagination=data.get("pagination")
            else:
                data=_read(opener,"https://my.prom.ua/cms/opinions/product/prom/context"
                           "?page=%d&perPage=20&sortingQuery=-date_created&pageType=portal"%page)
                ctx=data.get("context") or {}
                opinions=ctx.get("opinions")
                pagination=ctx.get("pagination")
            if not isinstance(opinions,list) or not isinstance(pagination,dict):
                raise ValueError("Некоректний список відгуків Prom")
            if page==1 and not opinions:
                raise ValueError("Prom повернув порожню першу сторінку — перевірка неповна")
            dates=[]
            for op in opinions:
                if not isinstance(op,dict) or str(op.get("companyId" if kind=="product" else "company_id"))!=str(shop.id):
                    raise ValueError("Prom повернув відгук іншого магазину")
                rid=str(op.get("id") or "")
                if not rid.isdigit() or rid in seen:raise ValueError("Повторний ID відгуку")
                seen.add(rid)
                raw=op.get("dateCreated" if kind=="product" else "date_created")
                try:dt=date.fromisoformat(str(raw)[:10])
                except ValueError:dt=None
                if dt:
                    dates.append(dt)
                    if previous and dt>previous:ordered=False
                    previous=dt
                else:ordered=False
                rating=op.get("rating")
                if type(rating) is not int or rating not in range(1,6):
                    continue
                oid=_order_id(op)
                if oid:found[oid].append({"rating":rating,"id":rid,"kind":kind})
            pages=int(pagination.get("num_pages") or 1)
            if page>=pages or (ordered and dates and max(dates)<earliest):break
            if not opinions:break
        else:raise ValueError("Prom: перевищено 200 сторінок")
    return found

def _worker(login_map,shop_book,run_id):
    global _state
    try:
        rows=_rows()
        roster=load_active_shops(shop_book,"Негативні відгуки")
        directory={normalize_name(shop.name):shop for shop in roster}
        groups=defaultdict(list)
        for row in rows:groups[normalize_name(row["shop"])].append(row)
        results=[]
        errors=[]
        for idx,(key,items) in enumerate(groups.items(),1):
            _state={"status":"running","run_id":run_id,
                    "message":f"Перевіряємо магазин {idx}/{len(groups)}: {items[0]['shop']}"}
            shop=directory.get(key)
            data=None
            if shop and login_map.get(str(shop.id)):
                for account in login_map[str(shop.id)]:
                    for attempt in range(3):
                        try:
                            data=_collect(shop,account,date(2026,1,1))
                            break
                        except Exception as exc:
                            print("[negative-hanging] shop=%s attempt=%s error=%s"%(key,attempt+1,type(exc).__name__),flush=True)
                            if attempt<2:time.sleep(1.5*(attempt+1))
                    if data is not None:break
            if data is None:errors.append(items[0]["shop"])
            for row in items:
                matches=data.get(row["order_id"],[]) if data is not None and row["order_id"] else []
                # An order may have multiple product reviews: ambiguous matches are not classified.
                unique={m["rating"] for m in matches}
                if data is None or not row["order_id"] or row["original_rating"] is None or not matches or len(unique)!=1:
                    status="не вдалося перевірити"
                    current=None
                else:
                    current=next(iter(unique))
                    status="оцінку змінено" if current!=row["original_rating"] else "ще не редагували"
                results.append({**row,"current_rating":current,"status":status})
        counts=dict(Counter(r["status"] for r in results))
        _state={"status":"partial" if errors or counts.get("не вдалося перевірити") else "success",
                "run_id":run_id,"message":"Перевірку завершено. Google-таблицю не змінено.",
                "total":len(results),"counts":counts,"results":results,
                "unavailable_shops":errors}
    except Exception as exc:
        _state={"status":"error","run_id":run_id,"message":str(exc)[:250]}
    finally:_lock.release()

def register(app,login_map_fn,shop_book_fn):
    @app.route("/negative/hanging/start",methods=["POST"])
    def negative_hanging_start():
        global _state
        if not _lock.acquire(False):
            return jsonify({"error":"Перевірка вже триває."}),409
        run_id=uuid.uuid4().hex
        _state={"status":"running","run_id":run_id,"message":"Читаємо висяки з Google-таблиці…"}
        try:
            mapping=login_map_fn()
            book=shop_book_fn()
            threading.Thread(target=_worker,args=(mapping,book,run_id),daemon=True).start()
        except Exception:
            _lock.release()
            raise
        return jsonify({"status":"started","run_id":run_id})

    @app.route("/negative/hanging/status",methods=["GET"])
    def negative_hanging_status():
        return jsonify(_state)
