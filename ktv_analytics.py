"""KTV analytics, adapted from the supplied ktv_import.py."""
import calendar
import re
import threading
import uuid
from collections import Counter
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from flask import jsonify, request
from negative_reviews import get_client

FIRST=date(2026,11,1)
EPOCH=date(1899,12,30)
SOURCE="1sNWKNZhmE-DXancPOX5RtLhtbQ_-ThwhfqlwyVmSzSE"
TARGET="1Ci_AoA6PBtlglbY_CY4d16tRX-7rxZ8_1YbEFft_hGs"
_lock=threading.Lock()
_state={"status":"idle"}

def norm(v):
    return " ".join(str(v or "").casefold().split())

def day_value(v,previous=FIRST):
    if isinstance(v,(int,float)) and 36526<=v<=73050:
        return EPOCH+timedelta(days=int(v))
    t=str(v or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}",t):
        return date.fromisoformat(t)
    m=re.fullmatch(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2}|\d{4}))?\.?",t)
    if not m:return None
    d,mo=map(int,m.group(1,2))
    y=m.group(3)
    return date(int(y)+(2000 if len(y)==2 else 0) if y else previous.year+int(previous.month==12 and mo==1),mo,d)

def at(row,i):
    return row[i] if i<len(row) else ""

def metrics(c):
    b,e,i,k=(c[x] for x in "BEIK")
    n=e+i+k
    def pct(a,b):return round(100*a/b,2) if b else None
    return {"orders":b,"successful":n,"success_pct":pct(n,b),"agreed":e,"agreed_pct":pct(e,n),"saved":i,"saved_pct":pct(i,i+k),"refused":k,"refused_pct":pct(k,n)}

def run(since,until,write):
    client=get_client()
    source=client.open_by_key(SOURCE).worksheet("КТВ")
    header=source.get("A1:E1")[0]
    if norm(at(header,0))!="дата" or "замовлення" not in norm(at(header,4)):
        raise ValueError("Змінилася структура КТВ (A, C, E).")
    dates=source.col_values(1,value_render_option="UNFORMATTED_VALUE")
    start=2
    for idx,v in enumerate(dates[1:],2):
        if isinstance(v,(int,float)) or re.search(r"(^\d{4}-|[./]\d{4}\.?$)",str(v)):
            d=day_value(v)
            if d and d>=FIRST:break
            if d:start=idx
    counts={}
    previous=None
    for lo in range(start,source.row_count+1,5000):
        hi=min(lo+4999,source.row_count)
        rows=source.get(f"A{lo}:E{hi}",value_render_option="UNFORMATTED_VALUE")
        for row in rows:
            d=day_value(at(row,0),previous or FIRST)
            if d:
                if previous and previous>=FIRST and d<previous:
                    raise ValueError("Порушена послідовність дат КТВ.")
                previous=d
            if not previous or previous<FIRST or not re.fullmatch(r"[0-9]{9,}",str(at(row,4)).strip()):continue
            if previous>datetime.now(ZoneInfo("Europe/Kyiv")).date():
                raise ValueError("У джерелі є майбутня дата.")
            c=counts.setdefault(previous,Counter())
            c["B"]+=1
            label=norm(at(row,2))
            if label in ("ок","ok"):c["E"]+=1
            elif label.startswith("врят"):c["I"]+=1
            elif label=="відмова":c["K"]+=1
    if not counts:raise ValueError("Немає датованих замовлень КТВ.")
    selected={}
    d=since
    while d<=until:
        selected[d]=counts.get(d,Counter())
        d+=timedelta(days=1)
    result={"summary":metrics(sum(selected.values(),Counter())),"days":[dict(date=str(d),**metrics(c)) for d,c in selected.items()]}
    if not write:return result
    book=client.open_by_key(TARGET)
    sheet=book.worksheet("Аналітика 2.0")
    if sheet.id!=1889689597:raise ValueError("Невірна вкладка аналітики.")
    h=sheet.get("A1:N2")
    # Current layout: grouped headings in row 1, individual metrics in row 2.
    expected={(1,0):"дата",(1,1):"к-ть ктв",(0,2):"успішні",(0,4):"погодилися чекати",(0,8):"відмови",(0,12):"забрані",(1,2):"к-ть",(1,3):"%",(1,4):"к-ть",(1,5):"%",(1,6):"к-ть забраних",(1,7):"%",(1,8):"к-ть врятованих",(1,9):"%",(1,10):"к-ть не врятованих",(1,11):"%",(1,12):"к-ть",(1,13):"%"}
    mismatches=[]
    for (r,c),v in expected.items():
        actual=norm(at(h[r],c)) if r<len(h) else ""
        if actual!=v:
            mismatches.append(f"{chr(65+c)}{r+1}: очікується «{v}», отримано «{actual or 'порожньо'}»")
    if mismatches:
        raise ValueError("Змінилися заголовки Аналітика 2.0: "+"; ".join(mismatches))
    rows=sheet.get("A3:L",value_render_option="UNFORMATTED_VALUE")
    positions={}
    blocks={}
    days=[]
    previous=FIRST
    for row,values in enumerate(rows,3):
        v=at(values,0)
        if not norm(v):
            if days:raise ValueError("Порожня дата всередині місячного блоку.")
            continue
        if norm(v)=="місяць":
            if not days:raise ValueError("Порожній місячний блок.")
            first=days[0][0]
            expected_days=[first.replace(day=n) for n in range(1,calendar.monthrange(first.year,first.month)[1]+1)]
            if [x[0] for x in days]!=expected_days or first in blocks:raise ValueError("Некоректний місячний блок.")
            blocks[first]=(days[0][1],row)
            for day,r in days:
                if day in positions:raise ValueError("Повторна дата.")
                positions[day]=r
            days=[]
            continue
        d=day_value(v,previous)
        if not d:raise ValueError("Нерозпізнана дата аналітики.")
        previous=d
        days.append((d,row))
    if days:raise ValueError("Немає підсумку Місяць.")
    updates=[]
    months=set()
    def add(r,c,value):
        updates.append({"range":f"{c}{r}","values":[[value]]})
    for d,c in selected.items():
        if d not in positions:raise ValueError("Немає місячного блоку для "+str(d)+". Створіть його перед записом.")
        r=positions[d]
        old=at(rows[r-3],1)
        if isinstance(old,(int,float)) and old>0 and d not in counts:
            raise ValueError("У джерелі зникли замовлення за "+str(d))
        for col in "BEIK":add(r,col,c[col])
        add(r,"C",f"=E{r}+I{r}+K{r}")
        for col,expr in {"D":f"C{r}/B{r}","F":f"E{r}/C{r}","J":f"I{r}/(I{r}+K{r})","L":f"K{r}/C{r}"}.items():
            add(r,col,f'=IFERROR({expr};"")')
        months.add(d.replace(day=1))
    for month in months:
        first,r=blocks[month]
        for col in "BCEIK":add(r,col,f"=SUM({col}{first}:{col}{r-1})")
        for col,expr in {"D":f"C{r}/B{r}","F":f"E{r}/C{r}","J":f"I{r}/(I{r}+K{r})","L":f"K{r}/C{r}"}.items():
            add(r,col,f'=IFERROR({expr};"")')
    sheet.batch_update(updates,value_input_option="USER_ENTERED")
    return result

def register(app):
    @app.post("/ktv/analytics/start")
    def ktv_analytics_start():
        global _state
        body=request.get_json(silent=True) or {}
        try:
            since=date.fromisoformat(body["since"])
            until=date.fromisoformat(body["until"])
            if since<FIRST or until<since or until>datetime.now(ZoneInfo("Europe/Kyiv")).date() or (until-since).days>90:raise ValueError()
        except (ValueError,KeyError,TypeError):
            return jsonify(error="Оберіть період від 01.11.2026 до сьогодні, максимум 91 день."),400
        if not _lock.acquire(False):return jsonify(error="Аналітика КТВ вже працює."),409
        run_id=uuid.uuid4().hex
        _state={"status":"running","run_id":run_id,"message":"Розраховуємо КТВ…"}
        def worker():
            global _state
            try:
                result=run(since,until,body.get("write") is True)
                _state=dict(result,status="success",run_id=run_id,message="Аналітику записано." if body.get("write") is True else "Аналітику розраховано.")
            except Exception as exc:
                _state={"status":"error","run_id":run_id,"message":str(exc)}
            finally:_lock.release()
        threading.Thread(target=worker,daemon=True).start()
        return jsonify(run_id=run_id)
    @app.get("/ktv/analytics/status")
    def ktv_analytics_status():
        return jsonify(_state)
