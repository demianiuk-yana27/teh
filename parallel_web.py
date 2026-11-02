import threading
import traceback
from datetime import datetime, timedelta

from flask import jsonify, render_template_string, request

import operations_web as ui

app = ui.app
base = ui.base

PROCESS_NAMES = {"reviews", "analytics", "order-check"}
process_locks = {name: threading.Lock() for name in PROCESS_NAMES}
process_statuses = {
    name: {"running": False, "process": name, "status": "idle", "message": ""}
    for name in PROCESS_NAMES
}


def _worker(process_name, sheet_id, since, until):
    try:
        if process_name == "reviews":
            result = base.run_review_export(sheet_id, since, until)
            message = (
                "Вигрузка відгуків завершена. "
                f"Знайдено: компанія — {result['collected_company']}, товари — {result['collected_product']}; "
                f"додано нових: {result['written']}. "
                f"Пропущено магазинів: {result['skipped']}; неповних перевірок: {result['incomplete']}."
            )
        elif process_name == "analytics":
            result = base.run_analytics(sheet_id)
            message = (
                "Аналітика та показник роботи завершені. "
                f"Записано магазинів: {result['written']}; пропущено: {result['skipped']}."
            )
        else:
            result = base.run_order_review_check(sheet_id, since, until)
            message = (
                "Перевірка на наявність відгуків завершена. "
                f"Перевірено: {result['checked']}; позначено «є відгук»: {result['written']}; "
                f"потребують уваги: {result['unresolved']}."
            )
        process_statuses[process_name] = {
            "running": False,
            "process": process_name,
            "status": "success",
            "message": message,
        }
    except Exception as exc:
        traceback.print_exc()
        process_statuses[process_name] = {
            "running": False,
            "process": process_name,
            "status": "error",
            "message": str(exc),
        }
    finally:
        process_locks[process_name].release()


def run_negative_parallel(process_name):
    if process_name not in PROCESS_NAMES:
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

    lock = process_locks[process_name]
    if not lock.acquire(blocking=False):
        return jsonify({"status": "busy", "message": "Цей процес уже виконується."}), 409

    try:
        sheet_id = base._sheet_id()
    except Exception as exc:
        lock.release()
        return jsonify({"status": "error", "message": str(exc)}), 400

    process_statuses[process_name] = {
        "running": True,
        "process": process_name,
        "status": "running",
        "message": "Процес виконується. Інші процеси Prom можна запускати паралельно.",
    }
    threading.Thread(
        target=_worker,
        args=(process_name, sheet_id, since, until),
        daemon=True,
    ).start()
    return jsonify({"status": "started", "message": "Процес запущено."})


def get_negative_status_parallel():
    process_name = str(request.args.get("process") or "").strip()
    if process_name not in PROCESS_NAMES:
        return jsonify({"status": "error", "message": "Невідомий процес."}), 400
    return jsonify(process_statuses[process_name])


# Замінюємо тільки обробники старих маршрутів, не створюючи дублікати URL.
app.view_functions["run_negative"] = run_negative_parallel
app.view_functions["get_negative_status"] = get_negative_status_parallel


PARALLEL_JS = r'''
<script>
const parallelNegativeTimers = {};

function negativeResultFor(processName) {
    if (processName === "order-check") return document.getElementById("orderCheckResult");
    if (processName === "reviews") return document.getElementById("reviewsResult");
    return document.getElementById("analyticsResult");
}

function ensureParallelResultBoxes() {
    const negative = document.getElementById("negativeSection");
    if (negative) {
        const reviewButton = Array.from(negative.querySelectorAll("button")).find(b => b.getAttribute("onclick") === "runNegative('reviews')");
        const analyticsButton = Array.from(negative.querySelectorAll("button")).find(b => b.getAttribute("onclick") === "runNegative('analytics')");
        [[reviewButton, "reviewsResult"], [analyticsButton, "analyticsResult"]].forEach(([button, id]) => {
            if (button && !document.getElementById(id)) {
                const box = document.createElement("div");
                box.id = id;
                box.style.cssText = "margin:8px 0 14px;font-weight:bold;white-space:pre-wrap;font-size:14px";
                const row = button.closest(".process-row");
                (row || button).insertAdjacentElement("afterend", box);
            }
        });
        const old = document.getElementById("negativeResult");
        if (old) old.style.display = "none";
    }

    const dial = document.getElementById("dialSection");
    if (dial && !document.getElementById("orderCheckResult")) {
        const button = Array.from(dial.querySelectorAll("button")).find(b => b.getAttribute("onclick") === "runNegative('order-check')");
        if (button) {
            const box = document.createElement("div");
            box.id = "orderCheckResult";
            box.style.cssText = "margin:8px 0 14px;font-weight:bold;white-space:pre-wrap;font-size:14px";
            const row = button.closest(".process-row");
            (row || button).insertAdjacentElement("afterend", box);
        }
    }
}

window.addEventListener("DOMContentLoaded", () => setTimeout(ensureParallelResultBoxes, 0));

function runNegative(processName) {
    ensureParallelResultBoxes();
    const result = negativeResultFor(processName);
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
        result.innerText = "❌ Виберіть дату.";
        return;
    }

    result.style.color = "#007bff";
    result.innerText = "⏳ Запускаємо процес...";
    fetch("/negative/run/" + processName, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({since, until})
    })
    .then(async response => {
        const data = await response.json();
        if (!response.ok && data.status !== "busy") throw new Error(data.message || "Не вдалося запустити процес.");
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
    if (parallelNegativeTimers[processName]) clearInterval(parallelNegativeTimers[processName]);
    parallelNegativeTimers[processName] = setInterval(() => {
        fetch("/negative/status?process=" + encodeURIComponent(processName))
        .then(response => response.json())
        .then(data => {
            const result = negativeResultFor(processName);
            if (data.status === "running") {
                result.style.color = "#007bff";
                result.innerText = "⏳ " + data.message;
            } else if (data.status === "success" || data.status === "error") {
                clearInterval(parallelNegativeTimers[processName]);
                delete parallelNegativeTimers[processName];
                result.style.color = data.status === "success" ? "green" : "red";
                result.innerText = (data.status === "success" ? "✅ " : "❌ ") + data.message;
            }
        });
    }, 2000);
}
</script>
'''


def _template():
    return ui._template().replace("</body>", PARALLEL_JS + "\n</body>")


def index_parallel():
    return render_template_string(
        _template(),
        default_reviews_date=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        default_negative_since=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        default_negative_until=datetime.now().strftime("%Y-%m-%d"),
    )


app.view_functions["index"] = index_parallel
