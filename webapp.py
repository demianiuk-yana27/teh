import threading
import traceback
from datetime import datetime, timedelta

from flask import jsonify, render_template_string, request

import app as legacy
from negative_reviews import run_analytics, run_order_review_check
from review_export import run_review_export

app = legacy.app
negative_lock = threading.Lock()
negative_status = {
    "running": False,
    "process": None,
    "status": "idle",
    "message": "",
}


def _negative_template():
    html = legacy.HTML_TEMPLATE

    html = html.replace(
        '''<button class="tab-btn" id="operationsTab"
                    onclick="switchTab('operations')">Операційні менеджери</button>''',
        '''<button class="tab-btn" id="operationsTab"
                    onclick="switchTab('operations')">Операційні менеджери</button>
            <button class="tab-btn" id="negativeTab"
                    onclick="switchTab('negative')">Негативні відгуки</button>''',
    )

    # Перевірка на наявність відгуків належить до процесів продзвону.
    order_check_section = '''

        <h4 style="margin-top:28px">Перевірка на наявність відгуків</h4>
        <div class="setting">
            <label for="orderCheckSince">📅 Дата початку перевірки:</label>
            <input type="date" id="orderCheckSince" value="{{ default_negative_since }}">
        </div>
        <div class="setting">
            <label for="orderCheckUntil">📅 Дата завершення перевірки:</label>
            <input type="date" id="orderCheckUntil" value="{{ default_negative_until }}">
        </div>
        <button class="btn" style="background:#b45309" onclick="runNegative('order-check')">
            🔎 Перевірка на наявність відгуків
        </button>
'''
    html = html.replace(
        '''        <button class="btn btn-3" onclick="runProcess(3)">
            💭 Запустити Процес 3 (Відгуки)
        </button>
        </section>''',
        '''        <button class="btn btn-3" onclick="runProcess(3)">
            💭 Запустити Процес 3 (Відгуки)
        </button>''' + order_check_section + '''
        </section>''',
    )

    negative_section = '''
        <section class="tab-section" id="negativeSection" style="display:none">
            <h3>Негативні відгуки</h3>

            <div class="setting">
                <label for="negativeReviewsDate">📅 Дата вигрузки відгуків:</label>
                <input type="date" id="negativeReviewsDate" value="{{ default_reviews_date }}">
            </div>

            <button class="btn" style="background:#7c3aed" onclick="runNegative('reviews')">
                ⭐ Вигрузка відгуків
            </button>

            <button class="btn" style="background:#0f766e" onclick="runNegative('analytics')">
                📊 Аналітика та показник роботи
            </button>

            <div id="negativeResult" style="margin-top:18px;font-weight:bold;white-space:pre-wrap"></div>
        </section>
'''
    html = html.replace('''        <div id="result"></div>''', negative_section + '''\n        <div id="result"></div>''')

    old_switch = '''function switchTab(tab) {
    const dialActive = tab === "dial";
    document.getElementById("dialSection").style.display = dialActive ? "block" : "none";
    document.getElementById("operationsSection").style.display = dialActive ? "none" : "block";
    document.getElementById("dialTab").classList.toggle("active", dialActive);
    document.getElementById("operationsTab").classList.toggle("active", !dialActive);
}'''
    new_switch = '''function switchTab(tab) {
    const dialActive = tab === "dial";
    const operationsActive = tab === "operations";
    const negativeActive = tab === "negative";
    document.getElementById("dialSection").style.display = dialActive ? "block" : "none";
    document.getElementById("operationsSection").style.display = operationsActive ? "block" : "none";
    document.getElementById("negativeSection").style.display = negativeActive ? "block" : "none";
    document.getElementById("dialTab").classList.toggle("active", dialActive);
    document.getElementById("operationsTab").classList.toggle("active", operationsActive);
    document.getElementById("negativeTab").classList.toggle("active", negativeActive);
}'''
    html = html.replace(old_switch, new_switch)

    negative_js = '''
let negativeTimer = null;

function runNegative(processName) {
    const negativeResult = document.getElementById("negativeResult");
    const result = processName === "order-check"
        ? document.getElementById("result")
        : negativeResult;

    let since = "";
    let until = "";

    if (processName === "reviews") {
        since = document.getElementById("negativeReviewsDate").value;
        until = since;
    } else if (processName === "order-check") {
        since = document.getElementById("orderCheckSince").value;
        until = document.getElementById("orderCheckUntil").value;
    }

    if ((processName === "reviews" || processName === "order-check") && !since) {
        result.style.color = "red";
        result.innerText = processName === "reviews" ? "❌ Виберіть дату вигрузки." : "❌ Виберіть дату початку.";
        return;
    }

    result.style.color = "#007bff";
    result.innerText = "⏳ Запускаємо процес...";

    fetch("/negative/run/" + processName, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({since: since, until: until})
    })
    .then(async response => {
        const data = await response.json();
        if (!response.ok && data.status !== "busy") {
            throw new Error(data.message || "Не вдалося запустити процес.");
        }
        return data;
    })
    .then(data => {
        if (data.status === "started") {
            result.style.color = "#007bff";
            result.innerText = "⏳ " + data.message;
            startNegativeStatusCheck(processName);
        } else {
            result.style.color = "orange";
            result.innerText = "⚠️ " + data.message;
        }
    })
    .catch(error => {
        result.style.color = "red";
        result.innerText = "❌ " + error.message;
    });
}

function startNegativeStatusCheck(processName) {
    if (negativeTimer) clearInterval(negativeTimer);
    negativeTimer = setInterval(() => {
        fetch("/negative/status")
        .then(response => response.json())
        .then(data => {
            const result = processName === "order-check"
                ? document.getElementById("result")
                : document.getElementById("negativeResult");
            if (data.status === "running") {
                result.style.color = "#007bff";
                result.innerText = "⏳ " + data.message;
            } else if (data.status === "success") {
                clearInterval(negativeTimer);
                negativeTimer = null;
                result.style.color = "green";
                result.innerText = "✅ " + data.message;
            } else if (data.status === "error") {
                clearInterval(negativeTimer);
                negativeTimer = null;
                result.style.color = "red";
                result.innerText = "❌ " + data.message;
            }
        });
    }, 2000);
}

'''
    html = html.replace('''function startStatusCheck() {''', negative_js + '''function startStatusCheck() {''')
    return html


def index_with_negative_reviews():
    default_reviews_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    default_negative_until = datetime.now().strftime("%Y-%m-%d")
    default_negative_since = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    return render_template_string(
        _negative_template(),
        default_reviews_date=default_reviews_date,
        default_negative_since=default_negative_since,
        default_negative_until=default_negative_until,
    )


app.view_functions["index"] = index_with_negative_reviews


def _sheet_id():
    value = (request.headers.get("X-Sheet-ID") or "").strip()
    if value:
        return value
    import os
    value = (os.environ.get("SHEET_ID") or os.environ.get("PROM_SHEET_ID") or "").strip()
    if not value:
        raise RuntimeError("У Render не задано SHEET_ID для таблиці Prom.")
    return value


def _negative_worker(process_name, sheet_id, since, until, run_id):
    global negative_status
    try:
        if process_name == "reviews":
            result = run_review_export(sheet_id, since, until)
            message = (
                "Вигрузка відгуків завершена. "
                f"Знайдено: компанія — {result['collected_company']}, товари — {result['collected_product']}; "
                f"додано нових: {result['written']}. "
                f"Пропущено магазинів: {result['skipped']}; неповних перевірок: {result['incomplete']}."
            )
        elif process_name == "analytics":
            result = run_analytics(sheet_id)
            message = (
                "Аналітика та показник роботи завершені. "
                f"Записано магазинів: {result['written']}; пропущено: {result['skipped']}."
            )
        elif process_name == "order-check":
            result = run_order_review_check(sheet_id, since, until)
            message = (
                "Перевірка на наявність відгуків завершена. "
                f"Перевірено: {result['checked']}; позначено «є відгук»: {result['written']}; "
                f"потребують уваги: {result['unresolved']}."
            )
        else:
            raise ValueError("Невідомий процес негативних відгуків.")
        from export_events import report_export
        report_export(
            "Негативні відгуки", run_id, result["written"],
            "відгуків" if process_name == "reviews" else "магазинів" if process_name == "analytics" else "замовлень",
            message,
        )
        negative_status = {
            "running": False,
            "process": process_name,
            "status": "success",
            "message": message,
            "run_id": run_id,
            "count": result["written"],
            "unit": "відгуків" if process_name == "reviews" else "магазинів" if process_name == "analytics" else "замовлень",
        }
    except Exception as exc:
        traceback.print_exc()
        negative_status = {
            "running": False,
            "process": process_name,
            "status": "error",
            "message": str(exc),
            "run_id": run_id,
        }
    finally:
        negative_lock.release()


@app.route("/negative/run/<process_name>", methods=["POST"])
def run_negative(process_name):
    global negative_status
    if process_name not in {"reviews", "analytics", "order-check"}:
        return jsonify({"status": "error", "message": "Невідомий процес."}), 400
    data = request.get_json(silent=True) or {}
    since = str(data.get("since") or "").strip()
    until = str(data.get("until") or "").strip()
    if process_name in {"reviews", "order-check"} and not since:
        return jsonify({"status": "error", "message": "Виберіть дату."}), 400
    if process_name == "reviews":
        until = since
    if since and until and since > until:
        return jsonify({"status": "error", "message": "Дата початку не може бути пізнішою за дату завершення."}), 400
    if not negative_lock.acquire(blocking=False):
        return jsonify({"status": "busy", "message": "Один із процесів негативних відгуків уже виконується."}), 409
    try:
        sheet_id = _sheet_id()
    except Exception as exc:
        negative_lock.release()
        return jsonify({"status": "error", "message": str(exc)}), 400
    run_id = __import__("uuid").uuid4().hex
    negative_status = {
        "run_id": run_id,
        "running": True,
        "process": process_name,
        "status": "running",
        "message": "Процес виконується. Не запускайте його повторно.",
    }
    thread = threading.Thread(
        target=_negative_worker,
        args=(process_name, sheet_id, since, until, run_id),
        daemon=True,
    )
    thread.start()
    return jsonify({"status": "started", "run_id": run_id, "message": "Процес запущено. Очікуємо завершення."})


@app.route("/negative/status")
def get_negative_status():
    return jsonify(negative_status)


import json as _diag_json
import os as _diag_os
import tempfile as _diag_tempfile
import time as _diag_time
import uuid as _diag_uuid

_DIAG_STATE_FILE = "/tmp/asteril_negative_diagnostic.json"
_DIAG_LOCK_FILE = "/tmp/asteril_negative_diagnostic.lock"

def _diag_write(state):
    fd, path = _diag_tempfile.mkstemp(prefix="asteril_diag_",dir="/tmp")
    try:
        with _diag_os.fdopen(fd,"w",encoding="utf-8") as handle:
            _diag_json.dump(state,handle,ensure_ascii=False)
        _diag_os.replace(path,_DIAG_STATE_FILE)
    finally:
        if _diag_os.path.exists(path):
            _diag_os.unlink(path)

def _diag_read():
    try:
        with open(_DIAG_STATE_FILE,encoding="utf-8") as handle:
            return _diag_json.load(handle)
    except (OSError,ValueError):
        return {"status":"idle","checks":[]}

def _diag_release():
    try:
        _diag_os.unlink(_DIAG_LOCK_FILE)
    except FileNotFoundError:
        pass

def _negative_diagnostic_checks(sheet_id,run_id):
    def progress(stage,checks):
        _diag_write({"status":"running","stage":stage,"checks":list(checks),"run_id":run_id,"started_at":_diag_time.time()})
    from negative_reviews import get_client, load_active_shops, PromBrowser
    checks = []
    progress("Перевіряємо Google Sheets",checks)
    try:
        client = get_client()
        book = client.open_by_key(sheet_id)
        checks.append({"name":"Google Sheets / авторизація","ok":True,"message":"Таблиця відкривається"})
    except Exception as exc:
        return {"ok":False,"checks":[{"name":"Google Sheets / авторизація","ok":False,"message":str(exc)[:250]}]}
    progress("Перевіряємо аркуші таблиці",checks)
    expected = ["Список магазинів","Аналітика відгуків","Показники роботи"]
    for title in expected:
        try:
            book.worksheet(title)
            checks.append({"name":"Аркуш: "+title,"ok":True,"message":"Знайдено"})
        except Exception:
            checks.append({"name":"Аркуш: "+title,"ok":False,"message":"Не знайдено"})
    try:
        from review_export import _sheet_name
        for kind, label in (("company","Відгуки про компанію"),("product","Відгуки про товари")):
            try:
                name = _sheet_name(book, kind)
                checks.append({"name":"Аркуш: "+label,"ok":True,"message":"Знайдено: "+name})
            except Exception as exc:
                checks.append({"name":"Аркуш: "+label,"ok":False,"message":str(exc)[:200]})
    except Exception as exc:
        checks.append({"name":"Аркуші відгуків","ok":False,"message":str(exc)[:200]})
    progress("Перевіряємо активні магазини",checks)
    shops = []
    try:
        shops = load_active_shops(sheet_id)
        checks.append({"name":"Активні магазини","ok":bool(shops),"message":"Знайдено: "+str(len(shops))})
    except Exception as exc:
        checks.append({"name":"Активні магазини","ok":False,"message":str(exc)[:200]})
    progress("Перевіряємо наявність авторизаційних файлів Prom",checks)
    import os as _prom_os
    from negative_reviews import _secret_path
    cookies_path=_secret_path("prom_cookies.json")
    cookies_present=_prom_os.path.isfile(cookies_path)
    if cookies_present:
        try:
            import json as _prom_json
            with open(cookies_path, "r", encoding="utf-8") as _prom_cookie_file:
                _prom_cookie_data = _prom_json.load(_prom_cookie_file)
            _prom_cookie_valid = isinstance(_prom_cookie_data, list) and bool(_prom_cookie_data) and all(
                isinstance(item, dict) and isinstance(item.get("name"), str)
                and isinstance(item.get("value"), str) for item in _prom_cookie_data
            )
            checks.append({"name":"Prom / файл cookies","ok":_prom_cookie_valid,"message":"Формат cookies коректний; дійсність сесії ще не підтверджена" if _prom_cookie_valid else "Файл знайдено, але формат cookies некоректний"})
        except (OSError, ValueError, TypeError):
            checks.append({"name":"Prom / файл cookies","ok":False,"message":"Файл знайдено, але не вдалося безпечно перевірити JSON"})
    else:
        checks.append({"name":"Prom / файл cookies","ok":False,"message":"Файл prom_cookies.json не знайдено"})
    profile_config=_prom_os.environ.get("PROM_PROFILE_PATH","").strip()
    profile_exists=bool(profile_config and _prom_os.path.isdir(profile_config))
    checks.append({"name":"Prom / профіль Chromium","ok":profile_exists,"message":"Налаштований профіль знайдено" if profile_exists else ("PROM_PROFILE_PATH заданий, але каталог відсутній" if profile_config else "PROM_PROFILE_PATH не заданий")})
    if not cookies_present and not profile_exists:
        checks.append({"name":"Prom / джерело авторизації","ok":False,"message":"Немає ні файлу cookies, ні доступного профілю; авторизація Prom не підтверджена"})
    progress("Перевіряємо HTTP-доступ до Prom",checks)
    try:
        import urllib.request as _prom_urlrequest
        import urllib.error as _prom_urlerror
        req = _prom_urlrequest.Request("https://my.prom.ua/cms/",headers={"User-Agent":"Mozilla/5.0 (compatible; AsterilDiagnostic/1.0)"},method="GET")
        try:
            with _prom_urlrequest.urlopen(req,timeout=12) as resp:
                code=resp.status
                final_url=resp.geturl()
        except _prom_urlerror.HTTPError as exc:
            code=exc.code
            final_url=exc.geturl()
        checks.append({"name":"Prom / HTTP-з'єднання","ok":True,"message":"HTTP "+str(code)+"; адреса: "+final_url[:110]+" (код не підтверджує авторизацію)"})
    except Exception as exc:
        checks.append({"name":"Prom / HTTP-з'єднання","ok":False,"message":str(exc)[:200]})
    progress("Перевіряємо поетапний HTTP-доступ Prom",checks)
    try:
        from negative_reviews import check_prom_http_session as _check_prom_http_session
        _http_ok, _http_message = _check_prom_http_session(timeout=12)
        checks.append({"name":"Prom / HTTP поетапно","ok":_http_ok,"message":_http_message})
    except Exception as exc:
        checks.append({"name":"Prom / HTTP поетапно","ok":False,"message":"Помилка діагностики: "+type(exc).__name__})
    progress("Запускаємо Chromium",checks)
    browser = None
    try:
        browser = PromBrowser()
        checks.append({"name":"Запуск Chromium","ok":True,"message":"Браузер запущено"})
        progress("Перевіряємо локальну сторінку Chromium",checks)
        browser.driver.set_page_load_timeout(12)
        browser.driver.get("data:text/html,<html><title>Asteril Browser Test</title><body>OK</body></html>")
        if browser.driver.title != "Asteril Browser Test":
            raise RuntimeError("Chromium не зміг відкрити локальну тестову сторінку")
        checks.append({"name":"Chromium / тестова сторінка","ok":True,"message":"Сторінка відкривається"})
        progress("Перевіряємо зовнішню сторінку Chromium",checks)
        try:
            browser.driver.set_page_load_timeout(12)
            browser.driver.get("https://example.com/")
            title=browser.driver.title or ""
            checks.append({"name":"Chromium / зовнішня сторінка","ok":"Example Domain" in title,"message":"Сторінка відкрилася" if "Example Domain" in title else "Сторінка відповіла, але заголовок неочікуваний"})
        except Exception as exc:
            checks.append({"name":"Chromium / зовнішня сторінка","ok":False,"message":str(exc).split("Stacktrace:")[0][:180]})
        progress("Перевіряємо cookies до переходу на Prom",checks)
        try:
            import json as _prom_json
            _prom_cookies = []
            if cookies_present:
                with open(cookies_path, "r", encoding="utf-8") as _prom_f:
                    _prom_cookies = _prom_json.load(_prom_f)
            _prom_allowed = []
            for _prom_cookie in _prom_cookies if isinstance(_prom_cookies, list) else []:
                if not isinstance(_prom_cookie, dict):
                    continue
                _prom_domain = str(_prom_cookie.get("domain", "")).lstrip(".").lower()
                if not (_prom_domain == "prom.ua" or _prom_domain.endswith(".prom.ua")):
                    continue
                if not isinstance(_prom_cookie.get("name"), str) or not isinstance(_prom_cookie.get("value"), str):
                    continue
                _prom_clean = {"name": _prom_cookie["name"], "value": _prom_cookie["value"], "domain": _prom_cookie.get("domain", "prom.ua"), "path": _prom_cookie.get("path", "/")}
                if isinstance(_prom_cookie.get("secure"), bool):
                    _prom_clean["secure"] = _prom_cookie["secure"]
                if isinstance(_prom_cookie.get("httpOnly"), bool):
                    _prom_clean["httpOnly"] = _prom_cookie["httpOnly"]
                _prom_allowed.append(_prom_clean)
            if _prom_allowed:
                browser.driver.execute_cdp_cmd("Network.enable", {})
                browser.driver.execute_cdp_cmd("Network.setCookies", {"cookies": _prom_allowed})
            checks.append({"name":"Prom / cookies до навігації","ok":bool(_prom_allowed) or profile_exists,"message":"Cookies для домену Prom встановлено до відкриття сайту" if _prom_allowed else ("Використовується профіль Chromium" if profile_exists else "У файлі немає cookies для домену Prom")})
        except Exception:
            checks.append({"name":"Prom / cookies до навігації","ok":False,"message":"Не вдалося застосувати cookies (секретні дані приховано)"})
        progress("Перевіряємо авторизацію Prom у Chromium",checks)
        try:
            # Use the same navigation as the actual exporter, including Cloudflare vault.
            # The older diagnostic used a 10-second WebDriver call that often timed out
            # before it could inspect the browser.
            browser.open_cms()
            checks.append({"name":"Prom / навігація після cookies","ok":True,"message":"Chromium відкрив кабінет; читання відгуків перевіряється окремо без навантаження на діагностику"})

        except Exception as exc:
            _prom_error = str(exc).split("Stacktrace:")[0].strip()[:180]
            checks.append({"name":"Prom / навігація після cookies","ok":False,"message":_prom_error or type(exc).__name__})

    except Exception as exc:
        checks.append({"name":"Chromium / запуск або тест","ok":False,"message":str(exc).split("Stacktrace:")[0][:220]})
    finally:
        if browser:
            browser.close()
    progress("Завершуємо перевірку",checks)
    return {"ok":all(c["ok"] for c in checks),"checks":checks,"note":"HTTP і швидка навігація не підтверджують авторизацію Prom. Дані не змінюються."}


def _negative_diagnostic_worker(sheet_id,run_id):
    try:
        result = _negative_diagnostic_checks(sheet_id,run_id)
        _diag_write({"status":"success","checks":result["checks"],"ok":result["ok"],"run_id":run_id})
    except Exception as exc:
        _diag_write({"status":"error","message":str(exc)[:250],"checks":[],"run_id":run_id})
    finally:
        _diag_release()

@app.route("/negative/diagnostic", methods=["POST"])
def negative_diagnostic():
    current = _diag_read()
    if current.get("status")=="running" and _diag_time.time()-current.get("started_at",0)<600:
        return jsonify(current)
    if _diag_os.path.exists(_DIAG_LOCK_FILE):
        try:
            if _diag_time.time()-_diag_os.stat(_DIAG_LOCK_FILE).st_mtime>600:
                _diag_release()
        except FileNotFoundError:
            pass
    try:
        fd=_diag_os.open(_DIAG_LOCK_FILE,_diag_os.O_CREAT|_diag_os.O_EXCL|_diag_os.O_WRONLY,0o600)
        _diag_os.close(fd)
    except FileExistsError:
        return jsonify(_diag_read())
    try:
        sheet_id=_sheet_id()
    except Exception as exc:
        _diag_release()
        result={"status":"success","ok":False,"checks":[{"name":"Налаштування таблиці","ok":False,"message":str(exc)}]}
        _diag_write(result)
        return jsonify(result)
    run_id=_diag_uuid.uuid4().hex
    state={"status":"running","message":"Перевіряємо Google Sheets і Prom","checks":[],"run_id":run_id,"started_at":_diag_time.time()}
    _diag_write(state)
    threading.Thread(target=_negative_diagnostic_worker,args=(sheet_id,run_id),daemon=True).start()
    return jsonify(state)

@app.route("/negative/diagnostic/status", methods=["GET"])
def negative_diagnostic_result():
    return jsonify(_diag_read())


# Separate read-only review test. The HTTP request never runs Chromium.
@app.route("/negative/review-probe", methods=["POST"])
def start_review_probe():
    import subprocess as _probe_subprocess
    import sys as _probe_sys
    import json as _probe_json
    lock = "/tmp/asteril_review_probe.lock"
    state_path = "/tmp/asteril_review_probe.json"
    try:
        fd = _diag_os.open(lock, _diag_os.O_CREAT | _diag_os.O_EXCL | _diag_os.O_WRONLY, 0o600)
        _diag_os.close(fd)
    except FileExistsError:
        try:
            age = _diag_time.time() - _diag_os.stat(lock).st_mtime
            if age < 300:
                return jsonify({"status": "running", "message": "Перевірка вже виконується"})
            _diag_os.unlink(lock)
        except OSError:
            pass
        return jsonify({"status": "error", "message": "Попередній процес завершився некоректно; повторіть запуск"}), 409
    state = {"status": "running", "stage": "Запускаємо окремий тест", "started_at": _diag_time.time()}
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            _probe_json.dump(state, f)
        probe_env = _diag_os.environ.copy()
        probe_env["REVIEW_PROBE_SHEET_ID"] = _sheet_id()
        try:
            _diag_os.unlink("/tmp/asteril_review_probe_metrics.json")
        except FileNotFoundError:
            pass
        probe_process = _probe_subprocess.Popen(
            [_probe_sys.executable, "-m", "review_read_probe"],
            stdin=_probe_subprocess.DEVNULL, stdout=_probe_subprocess.DEVNULL,
            stderr=_probe_subprocess.DEVNULL, close_fds=True, start_new_session=True,
            cwd=_diag_os.path.dirname(__file__) or ".", env=probe_env,
        )
        def _probe_sample(process):
            import json as _sample_json
            import time as _sample_time
            from pathlib import Path as _sample_path
            samples = []
            while process.poll() is None and len(samples) < 100:
                try:
                    cg = _sample_path("/sys/fs/cgroup/memory.current")
                    mem = int(cg.read_text().strip()) if cg.exists() else None
                    events_path = _sample_path("/sys/fs/cgroup/memory.events")
                    events = events_path.read_text().strip() if events_path.exists() else ""
                    chromium = 0
                    for proc in _sample_path("/proc").iterdir():
                        if proc.name.isdigit():
                            try:
                                cmd = (proc / "cmdline").read_bytes().lower()
                                if b"chromium" in cmd or b"chromedriver" in cmd:
                                    chromium += 1
                            except OSError:
                                pass
                    samples.append({"seconds": round(_sample_time.time() - state["started_at"], 1),
                                    "memory_mb": round(mem / 1048576, 1) if mem is not None else None,
                                    "chromium": chromium,
                                    "oom_kill": next((int(x.split()[1]) for x in events.splitlines() if x.startswith("oom_kill ")), None)})
                    tmp = "/tmp/asteril_review_probe_metrics.tmp"
                    with open(tmp, "w", encoding="utf-8") as f:
                        _sample_json.dump(samples, f)
                    _diag_os.replace(tmp, "/tmp/asteril_review_probe_metrics.json")
                    # Stop before the 512 MB cgroup limit makes the web service unresponsive.
                    if mem is not None and mem >= 450 * 1048576:
                        import signal as _probe_signal
                        try:
                            _diag_os.killpg(process.pid, _probe_signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        try:
                            with open(state_path, encoding="utf-8") as f:
                                latest = _sample_json.load(f)
                            latest.update(status="error", message="Тест зупинено: використання пам’яті досягло 450 МБ (захист сервера).")
                            temp_state = state_path + ".memory"
                            with open(temp_state, "w", encoding="utf-8") as f:
                                _sample_json.dump(latest, f, ensure_ascii=False)
                            _diag_os.replace(temp_state, state_path)
                        except (OSError, ValueError):
                            pass
                        try:
                            _diag_os.unlink(lock)
                        except FileNotFoundError:
                            pass
                        break
                except (OSError, ValueError):
                    pass
                _sample_time.sleep(2)
        threading.Thread(target=_probe_sample, args=(probe_process,), daemon=True).start()
        def _probe_watchdog(process):
            import signal as _probe_signal
            try:
                process.wait(timeout=90)
            except _probe_subprocess.TimeoutExpired:
                try:
                    _diag_os.killpg(process.pid, _probe_signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    with open(state_path, encoding="utf-8") as f:
                        latest = _probe_json.load(f)
                    if latest.get("status") == "running":
                        latest.update(status="error", message="Тест зупинено після 90 секунд. Chromium не завершився вчасно.")
                        with open(state_path + ".watchdog", "w", encoding="utf-8") as f:
                            _probe_json.dump(latest, f, ensure_ascii=False)
                        _diag_os.replace(state_path + ".watchdog", state_path)
                except (OSError, ValueError):
                    pass
                try:
                    _diag_os.unlink(lock)
                except FileNotFoundError:
                    pass
        threading.Thread(target=_probe_watchdog, args=(probe_process,), daemon=True).start()
        return jsonify(state), 202
    except Exception:
        try:
            _diag_os.unlink(lock)
        except OSError:
            pass
        return jsonify({"status": "error", "message": "Не вдалося запустити окрему перевірку"}), 500


@app.route("/negative/review-probe/status", methods=["GET"])
def review_probe_status():
    import json as _probe_json
    try:
        with open("/tmp/asteril_review_probe.json", encoding="utf-8") as f:
            state = _probe_json.load(f)
        if state.get("status") == "running" and _diag_time.time() - state.get("updated_at", state.get("started_at", 0)) > 90:
            return jsonify({"status": "error", "message": "Тест не відповідає. Не запускайте повторно до перевірки Render."})
        return jsonify(state)
    except (OSError, ValueError):
        return jsonify({"status": "idle"})


@app.route("/negative/system-health", methods=["GET"])
def negative_system_health():
    """Read-only Linux diagnostics; no Chromium or external service calls."""
    import os as _os
    import time as _time
    import json as _json
    import uuid as _uuid
    from pathlib import Path as _Path

    def _proc_rss_kb(pid):
        try:
            for line in _Path("/proc", str(pid), "status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
        except (OSError, ValueError, IndexError):
            pass
        return 0

    processes = []
    try:
        for entry in _os.scandir("/proc"):
            if not entry.name.isdigit():
                continue
            try:
                cmd = _Path(entry.path, "cmdline").read_bytes().replace(b"\\x00", b" ").decode("utf-8", "replace").lower()
                if "chromium" in cmd or "chromedriver" in cmd:
                    processes.append({"pid": int(entry.name), "rss_mb": round(_proc_rss_kb(entry.name) / 1024, 1)})
            except (OSError, ValueError):
                continue
    except OSError:
        pass

    memory = {}
    try:
        for line in _Path("/proc/meminfo").read_text().splitlines():
            key, _, value = line.partition(":")
            if key in ("MemTotal", "MemAvailable"):
                memory[key] = round(int(value.strip().split()[0]) / 1024, 1)
    except (OSError, ValueError, IndexError):
        pass

    cgroup = {}
    for key, paths in {
        "limit_bytes": ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
        "used_bytes": ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes"),
        "events": ("/sys/fs/cgroup/memory.events",),
    }.items():
        for path in paths:
            try:
                raw = _Path(path).read_text().strip()
                cgroup[key] = (int(raw) if raw.isdigit() else raw[:250])
                break
            except (OSError, ValueError):
                continue

    probe = {"status": "idle"}
    try:
        probe = _json.loads(_Path("/tmp/asteril_review_probe.json").read_text(encoding="utf-8"))
        if probe.get("status") == "running" and _time.time() - probe.get("updated_at", probe.get("started_at", 0)) > 90:
            probe = {"status": "stale", "stage": probe.get("stage", ""), "updated_at": probe.get("updated_at")}
    except (OSError, ValueError):
        pass

    try:
        uptime = round(float(_Path("/proc/uptime").read_text().split()[0]))
    except (OSError, ValueError, IndexError):
        uptime = None

    metrics = []
    try:
        metrics = _json.loads(_Path("/tmp/asteril_review_probe_metrics.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass

    return jsonify({
        "status": "ok", "instance_boot_id": _Path("/proc/sys/kernel/random/boot_id").read_text().strip()[:12] if _Path("/proc/sys/kernel/random/boot_id").exists() else None,
        "system_uptime_seconds": uptime, "worker_pid": _os.getpid(),
        "worker_rss_mb": round(_proc_rss_kb(_os.getpid()) / 1024, 1),
        "chromium_count": len(processes), "chromium_rss_mb": round(sum(p["rss_mb"] for p in processes), 1),
        "memory_host_mb": memory, "memory_cgroup": cgroup,
        "probe_metrics": metrics[-100:],
        "probe": {k: probe.get(k) for k in ("status", "stage", "updated_at", "message", "shop") if k in probe},
    })

@app.route("/negative/http-reviews-probe", methods=["GET"])
def negative_http_reviews_probe():
    """Read-only HTTP capability test; never switches the active Prom shop."""
    import http.cookiejar
    import urllib.request
    import urllib.error
    import urllib.parse
    from negative_reviews import _prom_session_cookies, COMPANY_REVIEWS_URL, PRODUCT_REVIEWS_URL
    try:
        cookies = _prom_session_cookies()
        jar = http.cookiejar.CookieJar()
        for item in cookies:
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain", "")).lower()
            if domain.lstrip(".") != "prom.ua" and not domain.lstrip(".").endswith(".prom.ua"):
                continue
            if not isinstance(item.get("name"), str) or not isinstance(item.get("value"), str):
                continue
            expiry = item.get("expirationDate", item.get("expiry"))
            try:
                expiry = int(expiry) if expiry is not None else None
            except (TypeError, ValueError):
                expiry = None
            jar.set_cookie(http.cookiejar.Cookie(
                version=0, name=item["name"], value=item["value"], port=None,
                port_specified=False, domain=domain, domain_specified=True,
                domain_initial_dot=domain.startswith("."), path=str(item.get("path", "/")),
                path_specified=True, secure=bool(item.get("secure", False)),
                expires=expiry, discard=expiry is None, comment=None,
                comment_url=None, rest={}, rfc2109=False))
        if not list(jar):
            return jsonify({"status": "error", "message": "Cookies Prom не знайдено"}), 200
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())
        results = []
        asset_cache = {}
        html_fingerprints = []
        # Cookie/no-cookie comparison is read-only and never returns body content.
        # Compare normalized markup to avoid incidental session-dependent tokens.
        def _anonymous_snapshot(target):
            req = urllib.request.Request(target, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            try:
                anon = urllib.request.build_opener(NoRedirect())
                try:
                    response = anon.open(req, timeout=5)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    status = response.code
                    content = response.read(120000).decode("utf-8", "replace") if status == 200 else ""
                    return status, content
            except (OSError, ValueError, TimeoutError):
                return None, ""
        def _normalized_markup(value):
            import re
            value = re.sub(r"<script\b[^>]*>.*?</script>", "", value, flags=re.I | re.S)
            value = re.sub(r"\s+", " ", value)
            return value.strip()
        for name, url in (("Компанія", COMPANY_REVIEWS_URL), ("Товари", PRODUCT_REVIEWS_URL)):
            request_obj = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml",
            })
            try:
                try:
                    response = opener.open(request_obj, timeout=8)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    code = response.code
                    mime = (response.headers.get("Content-Type") or "").split(";")[0].lower()
                    # Only inspect a bounded response body in memory; never return HTML or tokens.
                    body = response.read(120000).decode("utf-8", "replace").lower() if code == 200 else ""
                    location = response.headers.get("Location", "")
                    redirect_host = urllib.parse.urlsplit(urllib.parse.urljoin(url, location)).hostname if location else None
                    anon_status, anon_body = _anonymous_snapshot(url)
                    import difflib as _difflib
                    normalized_auth = _normalized_markup(body)
                    normalized_anon = _normalized_markup(anon_body.lower())
                    similarity = (_difflib.SequenceMatcher(
                        None, normalized_auth[:20000], normalized_anon[:20000],
                        autojunk=True).ratio() if code == 200 and anon_status == 200 else None)
                    cookie_comparison = {
                        "anonymous_http": anon_status,
                        "same_markup": normalized_auth == normalized_anon if similarity is not None else None,
                        "similarity_percent": round(similarity * 100) if similarity is not None else None,
                        "comparison_limit": "first 120 KB, normalized, scripts removed",
                    }
                    review_markup = any(x in body for x in ('statistics_block', 'opinion_stats_block', 'data-qaid="opinion', 'data-qaid="review'))
                    login_markup = ("пароль" in body or "password" in body) and ("увійти" in body or "войти" in body or "login" in body)
                    import re as _re
                    # Structural signals only: never return HTML, script URLs, JSON, tokens or personal data.
                    script_tags = _re.findall(r"<script\b[^>]*>", body)
                    external_scripts = sum("src=" in tag for tag in script_tags)
                    json_scripts = sum("application/json" in tag or "application/ld+json" in tag for tag in script_tags)
                    structure = {
                        "scripts_total": len(script_tags),
                        "scripts_external": external_scripts,
                        "json_scripts": json_scripts,
                        "next_state": "__next_data__" in body,
                        "nuxt_state": "__nuxt__" in body,
                        "initial_state": "__initial_state__" in body or "__preloaded_state__" in body,
                        "review_terms": any(term in body for term in ("review", "opinion", "відгук", "отзыв")),
                        "api_terms": any(term in body for term in ("/api/", "graphql", "fetch(", "axios")),
                        "shop_terms": any(term in body for term in ("company_id", "companyid", "shop_id", "shopid")),
                        "cabinet_terms": any(term in body for term in ("cabinet", "кабінет", "кабинет")),
                        "html_truncated": len(body.encode("utf-8")) >= 120000,
                    }
                    # Compare safe structural authentication hints without exposing shop IDs.
                    # Presence of a shop ID is only a hint, not proof of login.
                    visible_ids = _re.findall(r"\bid\s*[:№]\s*(\d{4,12})\b", body, _re.I)
                    structure["auth_hints"] = {
                        "shop_id_pattern": bool(visible_ids),
                        "shop_selector": any(x in body for x in ("company_info", "shop-selector", "company-switch")),
                        "logout_marker": any(x in body for x in ("logout", "signout", "вийти", "выйти")),
                        "login_form": login_markup,
                        "review_route_marker": "/cms/opinions/" in body,
                    }
                    # Count excluded script hosts only; do not fetch or expose their URLs.
                    excluded_hosts = set()
                    for tag in script_tags:
                        match = _re.search(r'\bsrc\s*=\s*["\x27]([^"\x27]+)', tag)
                        if not match:
                            continue
                        parsed = urllib.parse.urlsplit(urllib.parse.urljoin(url, match.group(1)))
                        if parsed.hostname not in ("my.prom.ua", "prom.ua"):
                            excluded_hosts.add(parsed.hostname or "unknown")
                    structure["external_script_hosts_count"] = len(excluded_hosts)
                    structure["excluded_script_tags"] = sum(
                        bool(_re.search(r'\bsrc\s*=', tag)) and
                        urllib.parse.urlsplit(urllib.parse.urljoin(
                            url, (_re.search(r'\bsrc\s*=\s*["\x27]([^"\x27]+)', tag) or ["", ""])[1]
                        )).hostname not in ("my.prom.ua", "prom.ua")
                        for tag in script_tags
                    )
                    import hashlib as _hashlib
                    html_fingerprints.append(_hashlib.sha256(body.encode("utf-8")).hexdigest())
                    # Scan up to nine same-origin JS assets without cookies; reuse results.
                    # Do not expose asset URLs, API paths, query strings or JS contents.
                    js_scan = {"checked": 0, "review_assets": 0, "api_assets": 0,
                               "fetch_assets": 0, "review_api_assets": 0, "errors": 0}
                    asset_urls = []
                    for tag in script_tags:
                        match = _re.search(r'\bsrc\s*=\s*["\x27]([^"\x27]+)', tag)
                        if not match:
                            continue
                        candidate = urllib.parse.urljoin(url, match.group(1))
                        parsed = urllib.parse.urlsplit(candidate)
                        if parsed.scheme != "https" or parsed.hostname not in ("my.prom.ua", "prom.ua"):
                            continue
                        if parsed.port not in (None, 443) or candidate in asset_urls:
                            continue
                        asset_urls.append(candidate)
                    anonymous = urllib.request.build_opener(NoRedirect())
                    js_scan["eligible_assets"] = len(asset_urls)
                    js_scan["skipped_assets"] = max(0, len(asset_urls) - 9)
                    for asset_url in asset_urls[:9]:
                        if asset_url in asset_cache:
                            cached = asset_cache[asset_url]
                            for key, value in cached.items():
                                js_scan[key] += value
                            continue
                        asset_result = {"checked": 0, "review_assets": 0, "api_assets": 0,
                                        "fetch_assets": 0, "review_api_assets": 0, "errors": 0}
                        try:
                            req = urllib.request.Request(asset_url, headers={
                                "User-Agent": "Mozilla/5.0",
                                "Accept": "application/javascript,text/javascript,*/*",
                            })
                            with anonymous.open(req, timeout=3) as js_response:
                                if js_response.status != 200:
                                    asset_result["errors"] += 1
                                    continue
                                js_type = (js_response.headers.get("Content-Type") or "").lower()
                                if not any(x in js_type for x in ("javascript", "text/plain", "application/octet-stream")):
                                    js_scan["errors"] += 1
                                    continue
                                js_body = js_response.read(250001)[:250000].decode("utf-8", "replace").lower()
                            asset_result["checked"] += 1
                            has_review = any(x in js_body for x in ("review", "opinion", "відгук", "отзыв"))
                            has_api = any(x in js_body for x in ("/api/", "graphql", "api/v"))
                            has_fetch = any(x in js_body for x in ("fetch(", "axios", "xmlhttprequest"))
                            asset_result["review_assets"] += int(has_review)
                            asset_result["api_assets"] += int(has_api)
                            asset_result["fetch_assets"] += int(has_fetch)
                            asset_result["review_api_assets"] += int(has_review and has_api)
                        except (OSError, ValueError, TimeoutError, urllib.error.HTTPError):
                            asset_result["errors"] += 1
                        finally:
                            asset_cache[asset_url] = asset_result
                            for key, value in asset_result.items():
                                js_scan[key] += value
                    structure["js_scan"] = js_scan
                    results.append({"type": name, "http": code, "content_type": mime,
                                    "review_markup": review_markup, "login_markup": login_markup,
                                    "redirect": "prom" if redirect_host in ("my.prom.ua", "prom.ua") else ("other" if redirect_host else "none"),
                                    "body_checked_bytes": min(len(body.encode("utf-8")), 120000),
                                    "html_structure": structure, "cookie_comparison": cookie_comparison})
            except (OSError, TimeoutError, ValueError) as exc:
                results.append({"type": name, "error": type(exc).__name__})
        return jsonify({"status": "ok", "results": results,
                        "html_identical": len(html_fingerprints) == 2 and html_fingerprints[0] == html_fingerprints[1],
                        "note": "HTTP-тест не перемикає магазин. Дані можуть належати поточному магазину сесії, а не Ладно. HTTP 200 не доводить авторизацію або читання відгуків."})
    except Exception:
        return jsonify({"status": "error", "message": "Не вдалося отримати або перевірити HTTP-сесію Prom. Секретні дані не показуються."})


@app.route("/negative/http-context-probe", methods=["GET"])
def negative_http_context_probe():
    """Read-only authenticated JSON check; never changes the selected shop or writes data."""
    import http.cookiejar
    import urllib.request
    import urllib.error
    from negative_reviews import _prom_session_cookies, COMPANY_REVIEWS_URL, PRODUCT_REVIEWS_URL

    try:
        jar = http.cookiejar.CookieJar()
        for item in _prom_session_cookies():
            if not isinstance(item, dict):
                continue
            domain = str(item.get("domain") or "").lower()
            if domain.lstrip(".") != "prom.ua" and not domain.lstrip(".").endswith(".prom.ua"):
                continue
            if not isinstance(item.get("name"), str) or not isinstance(item.get("value"), str):
                continue
            expiry = item.get("expirationDate", item.get("expiry"))
            try:
                expiry = int(expiry) if expiry is not None else None
            except (ValueError, TypeError):
                expiry = None
            jar.set_cookie(http.cookiejar.Cookie(
                version=0, name=item["name"], value=item["value"], port=None,
                port_specified=False, domain=domain, domain_specified=True,
                domain_initial_dot=domain.startswith("."), path=str(item.get("path") or "/"),
                path_specified=True, secure=bool(item.get("secure", False)),
                expires=expiry, discard=expiry is None, comment=None,
                comment_url=None, rest={}, rfc2109=False))
        if not list(jar):
            return jsonify({"status": "error", "message": "Cookies Prom не знайдено."})
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect())
        results = []
        for kind, base in (("company", COMPANY_REVIEWS_URL), ("product", PRODUCT_REVIEWS_URL)):
            for page in (1, 2) if kind == "company" else (1,):
                url = base + "/context?page=" + str(page) + "&per_page=20"
                req = urllib.request.Request(url, headers={
                    "Accept": "application/json, text/plain, */*",
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    "Referer": base,
                    "X-Requested-With": "XMLHttpRequest",
                })
                entry = {"type": kind, "page": page}
                try:
                    try:
                        response = opener.open(req, timeout=10)
                    except urllib.error.HTTPError as exc:
                        response = exc
                    with response:
                        entry["http"] = response.code
                        entry["content_type"] = (response.headers.get("Content-Type") or "").split(";")[0]
                        if response.code == 200:
                            raw = response.read(600001)
                            entry["oversized"] = len(raw) > 600000
                            if not entry["oversized"]:
                                try:
                                    payload = __import__("json").loads(raw)
                                except (ValueError, UnicodeDecodeError):
                                    payload = None
                                if isinstance(payload, dict):
                                    context = payload.get("context") or {}
                                    opinions = context.get("opinions") if isinstance(context, dict) else None
                                    pagination = context.get("pagination") if isinstance(context, dict) else None
                                    entry["json_ok"] = payload.get("status") == "ok"
                                    entry["opinions_count"] = len(opinions) if isinstance(opinions, list) else None
                                    entry["negative_count"] = sum(
                                        1 for x in opinions if isinstance(x, dict) and isinstance(x.get("rating"), int) and 1 <= x["rating"] <= 3
                                    ) if isinstance(opinions, list) else None
                                    entry["company_ids"] = sorted({
                                        str(x["company_id"]) for x in (opinions or [])
                                        if isinstance(x, dict) and x.get("company_id") is not None
                                    })[:5] if isinstance(opinions, list) else []
                                    if isinstance(pagination, dict):
                                        entry["pagination"] = {
                                            k: pagination.get(k) for k in ("current_page", "num_pages", "items_per_page", "item_count")
                                        }
                                    entry["first_opinion_id"] = next(
                                        (str(x.get("id")) for x in (opinions or []) if isinstance(x, dict) and x.get("id") is not None),
                                        None
                                    ) if isinstance(opinions, list) else None
                                else:
                                    entry["json_ok"] = False
                except (OSError, TimeoutError, ValueError) as exc:
                    entry["error"] = type(exc).__name__
                results.append(entry)
        first, second = results[0], results[1]
        pagination_verified = bool(
            first.get("json_ok") and second.get("json_ok")
            and first.get("pagination", {}).get("current_page") == 1
            and second.get("pagination", {}).get("current_page") == 2
            and first.get("first_opinion_id") != second.get("first_opinion_id")
        )
        return jsonify({
            "status": "ok", "results": results,
            "pagination_verified": pagination_verified,
            "note": "Лише читання; магазини не перемикаються, відгуки не записуються. Товари — непідтверджений endpoint.",
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": type(exc).__name__ + ": " + str(exc)[:180]})
