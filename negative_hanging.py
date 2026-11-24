"""Read-only review-edit follow-up report for negative-review managers."""
import re
import html
import json
import urllib.request
import urllib.error
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
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

def _sheet_review_date(value):
    raw=str(value or "").strip()
    for fmt in ("%d.%m.%Y","%d.%m.%y","%Y-%m-%d","%d.%m"):
        try:
            parsed=datetime.strptime(raw,fmt).date()
            return parsed.replace(year=2026) if fmt=="%d.%m" else parsed
        except ValueError:
            continue
    return None

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
                           "original_rating":original,"review_date":str(_sheet_review_date(row[6]) or ""),"review_text":str(row[8])[:220],
                           "link":str(row[11]).strip() if str(row[11]).strip().startswith("https://") else ""})
    return result


def _direct_review(opener, order_id, known_link=''):
    """Resolve the opinion from the order's context_misc JSON, then verify its rating."""
    if not str(order_id).isdigit():
        raise ValueError("invalid_order_id")
    headers={"User-Agent":"Mozilla/5.0","Accept":"application/json, text/html"}
    link_match=re.search(r'https?://(?:www\.)?prom\.ua/(?:ua/)?opinions/view/\d+',known_link or "")
    link=link_match.group(0) if link_match else None
    if not link:
        url="https://my.prom.ua/cms/order/edit/"+str(order_id)+"/context_misc"
        with opener.open(urllib.request.Request(url,headers=headers),timeout=12) as response:
            if not response.geturl().startswith(url):
                raise ValueError("context_redirect")
            raw=response.read(1500001)
            if len(raw)>1500000:
                raise ValueError("context_too_large")
        data=json.loads(raw.decode("utf-8"))
        # The review URL is inside processedMessage of client_left_opinion events.
        links=set()
        def walk(obj):
            if isinstance(obj,dict):
                if obj.get("actionType")=="client_left_opinion":
                    message=html.unescape(str(obj.get("processedMessage") or ""))
                    links.update(re.findall(r'https?://(?:www\.)?prom\.ua/(?:ua/)?opinions/view/\d+',message))
                for value in obj.values():
                    if isinstance(value,(dict,list)):
                        walk(value)
            elif isinstance(obj,list):
                for value in obj:
                    walk(value)
        walk(data)
        if len(links)!=1:
            raise ValueError("context_opinion_link_missing_or_ambiguous")
        link=next(iter(links))
    try:
        response=urllib.request.urlopen(urllib.request.Request(link,headers={"User-Agent":"Mozilla/5.0"}),timeout=12)
    except urllib.error.HTTPError as exc:
        if exc.code in (404,410):
            return {"rating":None,"link":link,"deleted":True}
        raise
    with response:
        raw=response.read(1000001)
        if len(raw)>1000000:
            raise ValueError("review_too_large")
        page=html.unescape(raw.decode("utf-8","replace"))
    # The public Prom opinion page embeds its authoritative opinion object in
    # window.ApolloCacheState, keyed by CompanyOpinionPageQuery.
    opinion_id=re.search(r'/opinions/view/(\d+)',link)
    if not opinion_id:
        raise ValueError("invalid_opinion_url")
    cache_match=re.search(r'window\.ApolloCacheState\s*=\s*',page)
    if not cache_match:
        raise ValueError("apollo_cache_missing")
    decoder=json.JSONDecoder()
    try:
        cache,_=decoder.raw_decode(page[cache_match.end():].lstrip())
    except (ValueError,TypeError):
        raise ValueError("apollo_cache_invalid")
    # Apollo caches can store query results in different nesting layouts.
    # Only accept objects with the exact opinion ID AND a valid own rating.
    expected_id=opinion_id.group(1)
    candidates=[]
    def inspect(node,depth=0):
        if depth>24:
            return
        if isinstance(node,dict):
            if str(node.get("id",""))==expected_id:
                rating=node.get("rating")
                company=node.get("company_id",node.get("companyId"))
                if type(rating) is int and 1<=rating<=5 and company is not None:
                    candidates.append((rating,str(company)))
            for value in node.values():
                if isinstance(value,(dict,list)):
                    inspect(value,depth+1)
        elif isinstance(node,list):
            for value in node:
                if isinstance(value,(dict,list)):
                    inspect(value,depth+1)
    inspect(cache)
    unique=set(candidates)
    if not unique:
        raise ValueError("opinion_id_or_rating_not_found_in_cache")
    if len(unique)!=1:
        raise ValueError("opinion_rating_ambiguous_in_cache")
    rating,company_id=next(iter(unique))
    return {"rating":rating,"link":link,"company_id":company_id}

def _opinion_status(op):
    """Read explicit Prom moderation/publication status; never infer deletion from stars."""
    values=[]
    for key in ("status","statusName","status_name","moderationStatus","moderation_status",
                "publicationStatus","publication_status","state","statusText","status_text",
                "statusLiteral","status_literal"):
        value=op.get(key)
        if isinstance(value,(str,int)):
            values.append(str(value).lower().replace("_"," ").replace("-"," "))
        elif isinstance(value,dict):
            values.extend(str(v).lower() for v in value.values() if isinstance(v,str))
    joined=" ".join(values)
    if op.get("deleted") is True or op.get("isRemovedByBuyer") is True or op.get("isRemovedByClient") is True or op.get("deletedByBuyer") is True:
        return "відгук видалено"
    if any(x in joined for x in ("видалено покупцем","удален покупателем","deleted by buyer","removed by buyer","deleted by client","removed by client")):
        return "відгук видалено"
    if op.get("isInApprovalPendingStatuses") is True or any(x in joined for x in ("очікує на публікацію","ожидает публикации","pending publication","awaiting publication")):
        return "очікує публікації"
    return None

def _collect(shop,account,earliest,progress=None,deadline=None,targets=None):
    opener,csrf=_switch(account)
    found=defaultdict(list)
    targets=set(targets or ())
    for kind in ("company","product"):
        previous=None
        ordered=True
        seen=set()
        for page in range(1,201):
            if deadline and time.monotonic()>deadline:
                raise TimeoutError("Ліміт часу перевірки магазину; результат не підтверджено")
            if progress:progress(kind,page)
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
                if oid:
                    # Safe diagnostic: only status-related fields, never buyer details.
                    status_fields={k:str(v)[:100] for k,v in op.items()
                                   if any(token in k.lower() for token in
                                          ("status","remov","delet","publish","approv","moderat","state"))
                                   and isinstance(v,(str,int,bool,dict))}
                    found[oid].append({"rating":rating,"id":rid,"kind":kind,
                                       "opinion_status":_opinion_status(op),
                                       "status_fields":status_fields})
            # Stop once each requested order has a matching review in both
            # categories scanned so far; do not traverse unrelated history.
            if targets and all(any(m.get("opinion_status")=="відгук видалено" or
                                   m.get("opinion_status")=="очікує публікації"
                                   for m in found.get(oid,[])) for oid in targets):
                return found
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
        direct_stats=Counter()
        direct_reasons=Counter()
        fallback_orders=[]
        for idx,(key,items) in enumerate(groups.items(),1):
            _state={"status":"running","run_id":run_id,
                    "message":f"Перевіряємо магазин {idx}/{len(groups)}: {items[0]['shop']}"}
            shop=directory.get(key)
            data=None
            direct={}
            if shop and login_map.get(str(shop.id)):
                # Fast path: inspect only the orders we need.
                try:
                    opener,_=_switch(login_map[str(shop.id)][0])
                    for n,item in enumerate(items,1):
                        _state={"status":"running","run_id":run_id,
                                "message":f"Магазин {idx}/{len(groups)}: {items[0]['shop']} · замовлення {n}/{len(items)}"}
                        try:
                            hit=_direct_review(opener,item["order_id"],item["link"])
                            if hit and hit.get("company_id") and str(hit["company_id"])!=str(shop.id):
                                raise ValueError("opinion_company_mismatch")
                            if hit:
                                direct[item["order_id"]]=hit
                                direct_stats["resolved"]+=1
                        except (ValueError,urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as exc:
                            direct_stats["fallback"]+=1
                            fallback_orders.append({"manager":item["manager"],"shop":item["shop"],
                                                    "order_id":item["order_id"],"tab":item["tab"],
                                                    "row":item["row"],"reason":str(exc)[:100] if isinstance(exc,ValueError) else type(exc).__name__,
                                                    "link":item["link"]})
                            reason=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
                            direct_reasons[reason[:70]]+=1
                            print("[negative-hanging] direct order=%s reason=%s"%(item["order_id"],reason[:70]),flush=True)
                except Exception as exc:
                    direct_reasons["shop_auth_"+type(exc).__name__]+=1
                    print("[negative-hanging] direct shop=%s error=%s"%(key,type(exc).__name__),flush=True)
                deadline=time.monotonic()+75
                def progress(kind,page):
                    global _state
                    _state={"status":"running","run_id":run_id,
                            "message":f"Магазин {idx}/{len(groups)}: {items[0]['shop']} · {kind} · сторінка {page}"}
                missing={item["order_id"] for item in items if item["order_id"] and item["order_id"] not in direct}
                pending_dates=[item["review_date"] for item in items if item["order_id"] in missing]
                earliest=(min(date.fromisoformat(d) for d in pending_dates)-timedelta(days=2)
                          if pending_dates and all(pending_dates) else date(2026,1,1))
                for account in (login_map[str(shop.id)] if missing else []):
                    for attempt in range(2):
                        if time.monotonic()>deadline:break
                        try:
                            data=_collect(shop,account,earliest,progress,deadline,
                                          missing)
                            break
                        except Exception as exc:
                            print("[negative-hanging] shop=%s attempt=%s error=%s"%(key,attempt+1,type(exc).__name__),flush=True)
                            if attempt<1 and time.monotonic()<deadline:time.sleep(1.5)
                    if data is not None:break
            if data is None and not direct:errors.append(items[0]["shop"])
            for row in items:
                hit=direct.get(row["order_id"])
                if not hit and data is not None and row["order_id"]:
                    for diagnostic in fallback_orders:
                        if diagnostic["order_id"]==row["order_id"] and diagnostic["shop"]==row["shop"]:
                            diagnostic["prom_status_fields"]=[
                                {"review_id":m.get("id"),"kind":m.get("kind"),
                                 "fields":m.get("status_fields",{})}
                                for m in data.get(row["order_id"],[])]
                matches=([hit] if hit else
                         data.get(row["order_id"],[]) if data is not None and row["order_id"] else [])
                # An order may have multiple product reviews: ambiguous matches are not classified.
                if hit and hit.get("deleted"):
                    results.append({**row,"current_rating":None,"status":"відгук видалено","link":hit["link"]})
                    continue
                statuses={m.get("opinion_status") for m in matches if m.get("opinion_status")}
                if statuses=={"відгук видалено"}:
                    results.append({**row,"current_rating":None,"status":"відгук видалено","link":row["link"]})
                    continue
                # An order can have multiple opinions over time. Without the original
                # opinion ID, a different rating is not proof that it was edited.
                if not hit and matches and any(m["rating"]!=row["original_rating"] for m in matches):
                    results.append({**row,"current_rating":None,"status":"не вдалося перевірити",
                                    "link":row["link"],
                                    "verification_note":"За замовленням знайдено іншу оцінку, але ID початкового відгуку невідомий"})
                    continue
                unique={m["rating"] for m in matches}
                if not row["order_id"] or row["original_rating"] is None or not matches or len(unique)!=1:
                    status="не вдалося перевірити"
                    current=None
                else:
                    current=next(iter(unique))
                    status="оцінку змінено" if current!=row["original_rating"] else "ще не редагували"
                results.append({**row,"current_rating":current,"status":status,"link":hit["link"] if hit else row["link"]})
        counts=dict(Counter(r["status"] for r in results))
        _state={"status":"partial" if errors or counts.get("не вдалося перевірити") else "success",
                "run_id":run_id,"message":"Перевірку завершено. Google-таблицю не змінено.",
                "total":len(results),"counts":counts,"results":results,
                "unavailable_shops":errors,
                "direct_resolved":direct_stats["resolved"],
                "direct_fallback":direct_stats["fallback"],
                "direct_reasons":dict(direct_reasons),
                "fallback_orders":fallback_orders}
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
