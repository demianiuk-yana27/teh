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
        progress("Відкриваємо Prom без очікування всіх ресурсів",checks)
        browser.driver.set_page_load_timeout(18)
        browser.driver.execute_cdp_cmd("Page.enable",{})
        # Set navigation strategy on the active Selenium session; do not alter export workers.
        try:
            browser.driver.execute_cdp_cmd("Page.navigate",{"url":"https://my.prom.ua/cms/"})
            import time as _prom_time
            _prom_time.sleep(5)
            current=browser.driver.current_url
            checks.append({"name":"Prom / швидка навігація","ok":"my.prom.ua" in current,"message":"Поточна адреса: "+current[:150]+"; авторизація не підтверджена"})
        except Exception as exc:
            checks.append({"name":"Prom / швидка навігація","ok":False,"message":str(exc).split("Stacktrace:")[0][:220]})
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
