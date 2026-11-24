"""Read-only 30-day company review analytics for the four call-center tabs."""
import threading
import time
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from flask import jsonify, request
from negative_reviews import get_client, normalize_name, normalize_order, parse_date
from call_review_preview import _shops, _switch, _read, _order_id, CALL_BOOK, TABS
from negative_reviews import Shop

_lock=threading.Lock()
_state={"status":"idle","message":"Готово до запуску."}
EXCLUDED={"смарт"}
EXCLUDED_SHOPS={"bybka_shop"}
LABELS=("так","нб","ні","є відгук","проста посилка","автовідповідач","смарт","нб2")
# Names used by call-center staff vs names in the Prom shop directory.
SHOP_ALIASES={
    "homstera (був market)":"homstera",
    "easyshop-дроп":"easyshop",
    "bybka_shop":"bybka",
    "toyvo - дроп":"toyvo",
    "botreba -дроп":"botreba",
    "botreba дроп":"botreba",
    "свій":"свій інтернет магазин",
    "borniatco":"borniatco🥇",
    "trendomania -дроп":"trendomania",
    "megashop -дроп":"megashop",
    "все для вас":"все для вас",
}

# The supplied sign-to account 44052893 is already mapped to company 3926531.
BORNIATCO_COMPANY_ID="3926531"
# Confirmed existing account mapping: sign-to 42325352 -> company 4093192.
TOYVO_COMPANY_ID="4093192"
# Existing sign-to 42640222 maps to company 4104969.
BOTREBA_COMPANY_ID="4104969"
SVIY_COMPANY_ID="4191142"

def _orders(start,end,write=False):
    book=get_client().open_by_key(CALL_BOOK)
    result=defaultdict(list)
    stats=Counter()
    good_choice_audit=defaultdict(Counter)
    for tab in TABS:
        # C:I includes hidden and filtered rows: Sheets API reads them normally.
        rows=book.worksheet(tab).get("C:I")
        for number,row in enumerate(rows,1):
            cells=(row+[""]*7)[:7]
            created=parse_date(cells[0][:10]) if cells[0] else None
            shop=normalize_name(cells[1])
            # Diagnose missing Good Choice without exposing order or customer details.
            shop_key="".join(ch for ch in shop if ch.isalnum())
            is_good_choice=("goodchoice" in shop_key or "goodchoise" in shop_key or "гудчойс" in shop_key or "гудchoice" in shop_key)
            if is_good_choice:
                good_choice_audit[tab]["all_rows"]+=1
                if not created:good_choice_audit[tab]["invalid_date"]+=1
                elif start<=created<=end:good_choice_audit[tab]["in_selected_period"]+=1
            if not created or not start<=created<=end:continue
            if shop in EXCLUDED_SHOPS and not write:
                stats["excluded_shop_rows"]+=1
                continue
            order=normalize_order(cells[5])
            external_id=normalize_order(cells[4])
            if is_good_choice and not (order or external_id):
                good_choice_audit[tab]["missing_order_id"]+=1
            if not shop or not (order or external_id):
                stats["missing_identity"]+=1
                if not write:continue
            label=normalize_name(cells[6]) or "без мітки"
            item={"tab":tab,"shop":shop,"order":order,"external_id":external_id,"created":created,
                  "label":label,"row":number}
            result[(shop,order or external_id)].append(item)
            stats["selected"]+=1
    return result,stats,{tab:dict(counts) for tab,counts in good_choice_audit.items()}

def _reviews(shop,account,start,end,current=False):
    opener,csrf=_switch(account)
    found=defaultdict(list)
    seen=set()
    inspected=0
    missing_order_ids=0
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
        if not opinions: return found,inspected,missing_order_ids
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
            if start<=published<=end and (not current or (opinion.get('deleted') is not True and str(opinion.get('status'))!='11')):
                inspected+=1
                order=_order_id(opinion)
                if order:found[order].append(published)
                else:missing_order_ids+=1
        pages=int(pagination.get("num_pages") or 1)
        if page>=pages or (ordered and dates and max(dates)<start):
            return found,inspected,missing_order_ids
    raise RuntimeError("Перевищено 200 сторінок Prom")

def _write_daily(start,end,orders,reviewed,run_id,mode):
    sheet=get_client().open_by_key("1Ci_AoA6PBtlglbY_CY4d16tRX-7rxZ8_1YbEFft_hGs").worksheet("Аналітика 2.0")
    dates=sheet.col_values(15)
    positions=defaultdict(list)
    for number,value in enumerate(dates,1):
        if number<3:continue
        raw=str(value).strip()
        parsed=None
        for fmt in ("%d.%m.%Y","%d.%m.%y","%Y-%m-%d","%d.%m"):
            try:
                parsed=datetime.strptime(raw,fmt).date()
                if fmt=="%d.%m":parsed=parsed.replace(year=start.year)
                break
            except ValueError:pass
        if parsed:positions[parsed].append(number)
    daily=defaultdict(Counter)
    missing_by_day=defaultdict(Counter)
    for (shop,_),entries in orders.items():
        for item in entries:
            c=daily[item["created"]]
            label=item["label"]
            c["orders"]+=1
            c["before"]+=label=="є відгук"
            c["success"]+=label in ("так","ні","проста посилка")
            c["negative"]+=label in ("ні","проста посилка")
            c["agreed"]+=label=="так"
            ids=[x for x in (item["order"],item["external_id"]) if x]
            if mode=="labels":continue
            if not ids or shop not in reviewed:
                c["unverified"]+=1
                reason="магазин не перевірено" if shop not in reviewed else "немає ID замовлення"
                missing_by_day[item["created"]][(shop or "невідомий магазин")+" ("+reason+")"]+=1
            elif any(d>=item["created"] for x in ids for d in reviewed[shop].get(x,[])):
                c["after"]+=1
    updates=[]
    incomplete=[]
    day=start
    while day<=end:
        if len(positions[day])!=1:
            raise ValueError("У колонці O немає єдиного рядка для "+day.isoformat())
        row=positions[day][0]
        c=daily[day]
        n=c["orders"]
        def pct(v):return (str(round(100*v/n,2)).replace(".",",")+"%") if n else "0%"
        values=[n,c["before"],pct(c["before"]),c["success"],pct(c["success"]),
                c["negative"],pct(c["negative"]),c["agreed"],pct(c["agreed"])]
        if c["unverified"]:
            incomplete.append(day.isoformat()+": "+str(c["unverified"])+" неперевірених; "+
                              ", ".join(k+" — "+str(v) for k,v in sorted(missing_by_day[day].items())))
        if mode=="labels":
            updates.append({"range":f"N{row}","values":[[n]]})
            updates.append({"range":f"P{row}:W{row}","values":[values[1:]]})
        else:
            updates.append({"range":f"X{row}:Y{row}","values":[[c["after"],pct(c["after"])]]})
        day+=timedelta(days=1)
    sheet.batch_update(updates,value_input_option="USER_ENTERED")
    return {"status":"partial" if incomplete else "success","run_id":run_id,
            "message":"Записано аналітику за вибрані дати. "+("N, P–W оновлено." if mode=="labels" else "X–Y оновлено.")+(" ⚠️ Часткові дані: "+"; ".join(incomplete) if incomplete else ""),
            "written_days":(end-start).days+1,"incomplete_dates":incomplete}

def _worker(start,end,login_map,run_id,write=False,mode=None):
    global _state
    try:
        orders,stats,good_choice_audit=_orders(start,end,write)
        if mode=="labels":
            _state=_write_daily(start,end,orders,{},run_id,mode)
            return
        shops=_shops()
        selected_shops={shop for shop,_ in orders}
        reviewed={}
        failures=[]
        unknown=[]
        diagnostics={}
        cutoff=date.today() if write else min(date.today(),end+timedelta(days=30))
        for i,shop in enumerate(sorted(selected_shops),1):
            _state={"status":"running","run_id":run_id,
                    "message":f"Перевіряємо магазини: {i}/{len(selected_shops)}"}
            directory_name=SHOP_ALIASES.get(shop,shop)
            info=shops.get(directory_name)
            if not info and shop=="свій":
                info=Shop("Свій інтернет магазин",SVIY_COMPANY_ID)
            if not info and shop=="borniatco":
                info=Shop("Borniatco",BORNIATCO_COMPANY_ID)
            if not info and shop=="toyvo - дроп":
                info=Shop("ToyVo",TOYVO_COMPANY_ID)
            if not info and shop=="botreba -дроп":
                info=Shop("BoTreba",BOTREBA_COMPANY_ID)
            if not info:
                unknown.append(shop)
                continue
            accounts=login_map.get(info.id) or []
            if not accounts:
                unknown.append(shop)
                continue
            for account in accounts:
                try:
                    # Some Prom shops intermittently fail to load opinions on the first request.
                    # Retry the whole read to avoid treating a partial page set as complete.
                    for attempt in range(3):
                        try:
                            found,inspected,missing_ids=_reviews(info,account,start,cutoff,write)
                            break
                        except Exception as transient:
                            print("[review-analytics] shop=%s attempt=%s/3 error=%s" %
                                  (shop,attempt+1,type(transient).__name__),flush=True)
                            if attempt==2:raise
                            time.sleep(1.5*(attempt+1))
                    reviewed[shop]=found
                    order_ids={identifier for (name,_),entries in orders.items() if name==shop for item in entries for identifier in (item["order"],item["external_id"]) if identifier}
                    matching_ids=order_ids.intersection(found)
                    diagnostics[shop]={"prom_reviews_in_period":inspected,
                        "prom_reviews_with_order_id":sum(len(v) for v in found.values()),
                        "prom_reviews_without_order_id":missing_ids,
                        "unique_matching_order_ids":len(matching_ids),
                        "selected_order_ids":len(order_ids)}
                    break
                except Exception as exc:
                    print("[review-analytics] failed shop=%s error=%s"%(shop,type(exc).__name__),flush=True)
            if shop not in reviewed:failures.append(shop)
        if write:
            _state=_write_daily(start,end,orders,reviewed,run_id,"reviews")
            return
        total_matches=sum(v["unique_matching_order_ids"] for v in diagnostics.values())
        suspicious_zero=bool(sum(v["prom_reviews_in_period"] for v in diagnostics.values()) and total_matches==0)
        total=Counter()
        per_tab=defaultdict(Counter)
        per_shop=defaultdict(Counter)
        per_label=defaultdict(Counter)
        today=date.today()
        for (shop,order),entries in orders.items():
            verified=shop in reviewed
            published=list({d for item in entries for identifier in (item["order"],item["external_id"]) if identifier for d in reviewed.get(shop,{}).get(identifier,[])})
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
                elif not verified or suspicious_zero:metrics.append("unverified")
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
        matched_total=sum(x["unique_matching_order_ids"] for x in diagnostics.values())
        inspected_total=sum(x["prom_reviews_in_period"] for x in diagnostics.values())
        no_matches=suspicious_zero
        def shape(counter):
            d=dict(counter)
            denom=d.get("finalized",0)-d.get("before_call",0)
            d["new_review_rate"]=round(100*d.get("new_after_processing",0)/denom,1) if denom>0 else None
            return d
        _state={"status":"partial" if failures or unknown or total["unverified"] or total["marked_but_not_found"] or no_matches else "success",
                "run_id":run_id,"since":start.isoformat(),"until":end.isoformat(),
                "message":"Перевірку завершено. Показники відображають стан Prom на момент перевірки.",
                "summary":shape(total),"by_tab":{k:shape(per_tab[k]) for k in TABS},
                "by_shop":{k:shape(v) for k,v in sorted(per_shop.items())},
                "by_label":{k:shape(v) for k,v in sorted(per_label.items())},
                "unavailable_shops":failures,"unmapped_shops":unknown,
                "missing_identity":stats["missing_identity"],
                "excluded_shop_rows":stats["excluded_shop_rows"],
                "good_choice_audit":good_choice_audit,
                "diagnostics_by_shop":diagnostics,
                "prom_reviews_inspected":inspected_total,
                "matching_order_ids":matched_total,
                "matching_warning":("Prom повернув відгуки, але жоден номер замовлення не збігся за колонками G або H. Результати перевірки Prom позначено як непідтверджені." if no_matches else ""),
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
            mode=body.get("mode")
            write=mode in ("labels","reviews") or body.get("write") is True
            mapping={} if mode=="labels" else login_map_fn()
            threading.Thread(target=_worker,args=(start,end,mapping,run_id,write,mode),daemon=True).start()
        except Exception:
            _lock.release()
            raise
        return jsonify({"status":"started","run_id":run_id})

    @app.route("/call-reviews/analytics/status",methods=["GET"])
    def call_reviews_analytics_status():
        return jsonify(_state)
