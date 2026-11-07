"""Send verified completion events from Render workers to Cloudflare D1.
Set EXPORT_EVENT_URL and EXPORT_EVENT_SECRET in Render environment; no credentials in source.
"""
import os
import time
import json
import logging
from urllib.request import Request, urlopen

def report_export(section, run_id, count, unit, message=""):
    url=os.environ.get("EXPORT_EVENT_URL","").strip()
    secret=os.environ.get("EXPORT_EVENT_SECRET","").strip()
    if not url or not secret:
        logging.warning("Export history disabled: EXPORT_EVENT_URL / EXPORT_EVENT_SECRET not configured")
        return False
    payload=json.dumps({"section":section,"run_id":run_id,"count":int(count),"unit":unit,"message":str(message)[:300]},ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        try:
            req=Request(url,data=payload,headers={"Content-Type":"application/json","X-Export-Secret":secret},method="POST")
            with urlopen(req,timeout=8) as response:
                result=json.loads(response.read().decode("utf-8"))
                if response.status==200 and result.get("ok"):
                    return True
        except Exception:
            logging.exception("Export completion callback failed (attempt %s)",attempt+1)
        if attempt<2:time.sleep(2*(attempt+1))
    logging.error("Export completion not recorded for run %s",run_id)
    return False
