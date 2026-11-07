"""Send verified completion events from Render workers to Cloudflare D1.
Set EXPORT_EVENT_URL and EXPORT_EVENT_SECRET in Render environment; no credentials in source.
"""
import os
import time
import json
import logging
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

def report_export(section, run_id, count, unit, message=""):
    url=os.environ.get("EXPORT_EVENT_URL","").strip()
    secret=os.environ.get("EXPORT_EVENT_SECRET","").strip()
    if not url or not secret:
        logging.warning("Export history disabled: EXPORT_EVENT_URL / EXPORT_EVENT_SECRET not configured")
        return False
    if not run_id:
        run_id=uuid.uuid4().hex
        logging.warning("Missing export run_id; generated fallback id %s for %s",run_id,section)
    payload=json.dumps({"section":section,"run_id":run_id,"count":int(count),"unit":unit,"message":str(message)[:300]},ensure_ascii=False).encode("utf-8")
    for attempt in range(3):
        try:
            req=Request(url,data=payload,headers={"Content-Type":"application/json","X-Export-Secret":secret,"User-Agent":"Asteril-Export-Reporter/1.0","Accept":"application/json"},method="POST")
            with urlopen(req,timeout=8) as response:
                result=json.loads(response.read().decode("utf-8"))
                if response.status==200 and result.get("ok"):
                    return True
        except HTTPError as error:
            body=error.read(800).decode("utf-8","replace")
            logging.error("Export callback HTTP %s (attempt %s/3): content-type=%s, response=%r, run=%s",error.code,attempt+1,error.headers.get("Content-Type"),body,run_id)
            if error.code in (400,401,403,404,405,422):
                break
        except URLError as error:
            logging.error("Export callback connection failure (attempt %s/3): %s",attempt+1,error.reason)
        except Exception:
            logging.exception("Export completion callback failed (attempt %s/3)",attempt+1)
        if attempt<2:time.sleep(2*(attempt+1))
    logging.error("Export completion not recorded for run %s",run_id)
    return False
