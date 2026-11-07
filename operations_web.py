from datetime import datetime, timedelta
from flask import jsonify, render_template_string

import webapp as base
from order_count_report import run_order_count_report

app = base.app


def _template():
    html = base._negative_template()
    block = '''
            <h4 style="margin-top:30px">Звіт по кількості замовлень</h4>
            <button class="btn" style="background:#2563eb" onclick="runOrderCountReport()">
                📊 Звіт по кількості замовлень
            </button>
'''
    html = html.replace(
        '''            <button class="btn btn-4" onclick="runProcess(4)">
                📋 Запустити вивантаження «Доробки»
            </button>
        </section>''',
        '''            <button class="btn btn-4" onclick="runProcess(4)">
                📋 Запустити вивантаження «Доробки»
            </button>\n''' + block + '''
        </section>''',
    )

    design_css = '''
    <style>
        body { margin:0; padding:56px 20px; box-sizing:border-box; }
        .container { display:block; width:825px; max-width:100%; margin:0 auto; padding:48px 50px; box-sizing:border-box; }
        .setting select, .setting input[type="date"] {
            width:190px; height:46px; padding:0 14px; border:1px solid #d7dee8; border-radius:8px;
            background:#f8fafc; color:#1f2937; font:inherit; font-size:16px; outline:none; box-sizing:border-box;
            transition:border-color .2s ease, box-shadow .2s ease, background .2s ease;
        }
        .setting select { cursor:pointer; }
        .setting select:hover, .setting input[type="date"]:hover { border-color:#9fb4cc; background:#fff; }
        .setting select:focus, .setting input[type="date"]:focus { border-color:#1f5f9f; background:#fff; box-shadow:0 0 0 3px rgba(31,95,159,.12); }

        .process-row { display:flex; justify-content:center; align-items:center; gap:24px; margin:18px 0; }
        .process-row > .btn { width:350px; margin:0; flex:0 0 350px; }
        .process-control { width:260px; flex:0 0 260px; text-align:left; transform:translateY(-10px); }
        .process-control .setting { margin:0; }
        .process-control .setting label { display:block; margin:0 0 7px; font-size:14px; }

        .range-box {
            width:260px; height:54px; border:1px solid #d7dee8; border-radius:8px; background:#f8fafc;
            display:flex; align-items:center; justify-content:center; gap:7px; padding:0 10px; box-sizing:border-box;
        }
        .range-box input[type="date"] {
            width:105px; min-width:0; height:38px; padding:0 5px; border:0; background:transparent; font:inherit; font-size:13px; outline:none;
        }
        .range-box .range-separator { color:#64748b; font-weight:700; }
        .range-label { display:block; margin:0 0 7px; font-size:14px; font-weight:700; }

        @media (max-width:700px) {
            body { padding:20px 12px; }
            .container { padding:30px 20px; }
            .process-row { flex-direction:column; gap:10px; }
            .process-row > .btn, .process-control { width:100%; flex:auto; }
            .process-control { transform:none; }
            .range-box { width:100%; }
        }
    </style>
'''
    html = html.replace('</head>', design_css + '\n</head>')

    layout_js = '''
<script>
window.addEventListener("DOMContentLoaded", function () {
    function makeRow(section, button, control) {
        if (!section || !button || !control || button.closest(".process-row")) return;
        const row = document.createElement("div");
        row.className = "process-row";
        button.parentNode.insertBefore(row, button);
        row.appendChild(button);
        row.appendChild(control);
    }

    function wrapSetting(setting) {
        if (!setting) return null;
        const control = document.createElement("div");
        control.className = "process-control";
        control.appendChild(setting);
        return control;
    }

    const dial = document.getElementById("dialSection");
    if (dial) {
        const ktvButton = dial.querySelector(".btn-1");
        const reviewButton = dial.querySelector(".btn-3");
        const settings = Array.from(dial.querySelectorAll(":scope > .setting"));
        if (ktvButton && settings[0]) makeRow(dial, ktvButton, wrapSetting(settings[0]));
        if (reviewButton && settings[1]) makeRow(dial, reviewButton, wrapSetting(settings[1]));

        const since = document.getElementById("orderCheckSince");
        const until = document.getElementById("orderCheckUntil");
        const checkButton = Array.from(dial.querySelectorAll("button")).find(b => b.getAttribute("onclick") === "runNegative('order-check')");
        if (since && until && checkButton) {
            const sinceSetting = since.closest(".setting");
            const untilSetting = until.closest(".setting");
            const heading = Array.from(dial.querySelectorAll("h4")).find(h => h.textContent.includes("Перевірка на наявність відгуків"));
            if (heading) heading.remove();

            const control = document.createElement("div");
            control.className = "process-control";
            const label = document.createElement("span");
            label.className = "range-label";
            label.textContent = "📅 Період перевірки:";
            const box = document.createElement("div");
            box.className = "range-box";
            const sep = document.createElement("span");
            sep.className = "range-separator";
            sep.textContent = "—";
            box.appendChild(since);
            box.appendChild(sep);
            box.appendChild(until);
            control.appendChild(label);
            control.appendChild(box);
            if (sinceSetting) sinceSetting.remove();
            if (untilSetting) untilSetting.remove();
            makeRow(dial, checkButton, control);
        }
    }

    const operations = document.getElementById("operationsSection");
    if (operations) {
        const button = operations.querySelector(".btn-4");
        const setting = operations.querySelector(":scope > .setting");
        if (button && setting) makeRow(operations, button, wrapSetting(setting));
    }

    const negative = document.getElementById("negativeSection");
    if (negative) {
        const button = Array.from(negative.querySelectorAll(":scope > button")).find(b => b.getAttribute("onclick") === "runNegative('reviews')");
        const setting = negative.querySelector(":scope > .setting");
        if (button && setting) makeRow(negative, button, wrapSetting(setting));
    }
});
</script>
'''
    html = html.replace('</body>', layout_js + '\n</body>')

    js = '''
function runOrderCountReport() {
    const result = document.getElementById("result");
    result.style.color = "#007bff";
    result.innerText = "⏳ Формуємо звіт по кількості замовлень...";
    fetch("/operations/order-count-report", {method: "POST"})
      .then(async response => {
          const data = await response.json();
          if (!response.ok) throw new Error(data.message || "Помилка запуску звіту.");
          return data;
      })
      .then(data => { result.style.color = "green"; result.innerText = "✅ " + data.message; })
      .catch(error => { result.style.color = "red"; result.innerText = "❌ " + error.message; });
}

'''
    return html.replace('''function startStatusCheck() {''', js + '''function startStatusCheck() {''')


def index_with_operations():
    return render_template_string(
        _template(),
        default_reviews_date=(datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
        default_negative_since=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        default_negative_until=datetime.now().strftime("%Y-%m-%d"),
    )


app.view_functions["index"] = index_with_operations


@app.route("/operations/order-count-report", methods=["POST"])
def order_count_report_endpoint():
    legacy = base.legacy
    if not legacy.process_lock.acquire(blocking=False):
        return jsonify({"status":"busy","message":"Зараз уже виконується інший процес Asteril. Дочекайтеся його завершення."}), 409
    try:
        result = run_order_count_report()
        from export_events import report_export
        report_export("Звіт по кількості замовлень", __import__("uuid").uuid4().hex,
                      int(result["statuses"]), "статусів",
                      f"Звіт оновлено за {result['date']}. Записано статусів: {result['statuses']}.")
        return jsonify({"status":"success","message":f"Звіт оновлено за {result['date']}. Записано статусів: {result['statuses']}."})
    except Exception as exc:
        return jsonify({"status":"error","message":str(exc)}), 500
    finally:
        legacy.process_lock.release()
