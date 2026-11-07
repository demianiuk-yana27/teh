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
