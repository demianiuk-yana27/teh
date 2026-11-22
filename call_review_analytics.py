"""Read-only 30-day company review analytics for the four call-center tabs."""
import threading
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from flask import jsonify, request
from negative_reviews import get_client, normalize_name, normalize_order, parse_date
from call_review_preview import _shops, _switch, _read, _order_id, CALL_BOOK, TABS

_lock=threading.Lock()
_state={"status":"idle","message":"Готово до запуску."}
EXCLUDED={"смарт"}
LABELS=("так","нб","ні","є відгук","проста посилка","автовідповідач","смарт","нб2")

def _orders(start,end):
    book=get_client().open_by_key(CALL_BOOK)
    result=defaultdict(list)
    stats=Counter()
    for tab in TABS:
        # C:I includes hidden and filtered rows: Sheets API reads them normally.
        rows=book.worksheet(tab).get("C:I")
        for number,row in enumerate(rows,1):
            cells=(row+[""]*7)[:7]
            created=parse_date(cells[0][:10]) if cells[0] else None
            if not created or not start<=created<=end:continue
            shop=normalize_name(cells[1])
            order=normalize_order(cells[5])
            if not shop or not order:
                stats["missing_identity"]+=1
                continue
            label=normalize_name(cells[6]) or "без мітки"
            item={"tab":tab,"shop":shop,"order":order,"created":created,
                  "label":label,"row":number}
            result[(shop,order)].append(item)
            stats["selected"]+=1
    return result,stats

def _reviews(shop,account,start,end):
    opener,csrf=_switch(account)
    found=defaultdict(list)
    seen=set()
    previous=None
    ordered=True
    for page in range(1,201):
        data=_read(opener,"https://my.prom.ua/cms/opinions/company/list",
                   {"filters":[],"page":page,"pageType":"portal","perPage":20,
                    "searchQuery":"","sortingQuery":"default"},csrf)
        opinions=data.get("opinions")
        pagination=data.get("pagination")
        if not isinstance(opinions,list) or not isinstance(pagination,dict):
            raise RuntimeError("Некоректна відповідь Prom")
        if not opinions: return found
        dates=[]
        for opinion in opinions:
            if not isinstance(opinion,dict) or str(opinion.get("company_id"))!=shop.id:
                raise RuntimeError("Prom повернув дані іншого магазину")
            rid=str(opinion.get("id") or "")
            if not rid.isdigit() or rid in seen:raise RuntimeError("Повторний або невідомий ID відгуку")
            seen.add(rid)
            published=parse_date(str(opinion.get("date_created") or "")[:10])
            if not published:
                ordered=False
                continue
            dates.append(published)
            if previous is not None and published>previous:ordered=False
            previous=published
            if start<=published<=end:
                order=_order_id(opinion)
                if order:found[order].append(published)
        pages=int(pagination.get("num_pages") or 1)
        if page>=pages or (ordered and dates and max(dates)<start):
            return found
    raise RuntimeError("Перевищено 200 сторінок Prom")

def _worker(start,end,login_map,run_id):
    global _state
    try:
        orders,stats=_orders(start,end)
        shops=_shops()
        selected_shops={shop for shop,_ in orders}
        reviewed={}
        failures=[]
        unknown=[]
        cutoff=min(date.today(),end+timedelta(days=30))
        for i,shop in enumerate(sorted(selected_shops),1):
            _state={"status":"running","run_id":run_id,
                    "message":f"Перевіряємо магазини: {i}/{len(selected_shops)}"}
            info=shops.get(shop)
            if not info:
                unknown.append(shop)
                continue
            accounts=login_map.get(info.id) or []
            if not accounts:
                unknown.append(shop)
                continue
            for account in accounts:
                try:
                    reviewed[shop]=_reviews(info,account,start,cutoff)
                    break
                except Exception as exc:
                    print("[review-analytics] failed shop=%s error=%s"%(shop,type(exc).__name__),flush=True)
            if shop not in reviewed:failures.append(shop)
        total=Counter()
        per_tab=defaultdict(Counter)
        per_shop=defaultdict(Counter)
        per_label=defaultdict(Counter)
        today=date.today()
        for (shop,order),entries in orders.items():
            verified=shop in reviewed
            published=reviewed.get(shop,{}).get(order,[])
            for item in entries:
                label=item["label"]
                mature=item["created"]+timedelta(days=30)<today
                eligible=label not in EXCLUDED
                # A review published on/before day 30 is counted even if it was later removed.
                has_review=any(item["created"]<=d<=item["created"]+timedelta(days=30) for d in published)
                before=label=="є відгук"
                metrics=["orders"]
                if not eligible:metrics.append("excluded")
                elif not mature:metrics.append("pending_30_days")
                elif not verified:metrics.append("unverified")
                else:
                    metrics.append("finalized")
                    if before:metrics.append("before_call")
                    if has_review:metrics.append("prom_review_30_days")
                    if has_review and not before:metrics.append("new_after_processing")
                    if before and not has_review:metrics.append("marked_but_not_found")
                    if not has_review and not before:metrics.append("without_review")
                for key in metrics:
                    total[key]+=1
                    per_tab[item["tab"]][key]+=1
                    per_shop[shop][key]+=1
                    per_label[label][key]+=1
        def shape(counter):
            d=dict(counter)
            denom=d.get("finalized",0)-d.get("before_call",0)
            d["new_review_rate"]=round(100*d.get("new_after_processing",0)/denom,1) if denom>0 else None
            return d
        _state={"status":"partial" if failures or unknown or total["unverified"] or total["marked_but_not_found"] else "success",
                "run_id":run_id,"since":start.isoformat(),"until":end.isoformat(),
                "message":"Перевірку завершено. Показники відображають стан Prom на момент перевірки.",
                "summary":shape(total),"by_tab":{k:shape(per_tab[k]) for k in TABS},
                "by_shop":{k:shape(v) for k,v in sorted(per_shop.items())},
                "by_label":{k:shape(v) for k,v in sorted(per_label.items())},
                "unavailable_shops":failures,"unmapped_shops":unknown,
                "missing_identity":stats["missing_identity"],
                "note":"Проміжні дані до 30-го дня не фіналізуються. Мітка «є відгук» є історичним свідченням; відсутність відгуку в Prom зараз не доводить, що його не було раніше. Новий відгук після опрацювання не доводить причинності дзвінка."}
    except Exception as exc:
        _state={"status":"error","run_id":run_id,"message":str(exc)[:300]}
    finally:
        _lock.release()

def register(app,login_map_fn):
    @app.route("/call-reviews/analytics/start",methods=["POST"])
    def call_reviews_analytics_start():
        global _state
        body=request.get_json(silent=True) or {}
        start=parse_date(body.get("since"))
        end=parse_date(body.get("until"))
        if not start or not end or start>end:return jsonify({"error":"Невірний діапазон дат"}),400
        if end>date.today():return jsonify({"error":"Майбутні дати не підтримуються"}),400
        if (end-start).days>90:return jsonify({"error":"Максимальний діапазон — 90 днів"}),400
        if not _lock.acquire(False):return jsonify({"error":"Аналітика вже виконується"}),409
        run_id=uuid.uuid4().hex
        _state={"status":"running","run_id":run_id,"message":"Зчитуємо таблиці продзвону…"}
        try:
            mapping=login_map_fn()
            threading.Thread(target=_worker,args=(start,end,mapping,run_id),daemon=True).start()
        except Exception:
            _lock.release()
            raise
        return jsonify({"status":"started","run_id":run_id})

    @app.route("/call-reviews/analytics/status",methods=["GET"])
    def call_reviews_analytics_status():
        return jsonify(_state)
