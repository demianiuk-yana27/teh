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
        body {
            margin: 0;
            padding: 56px 20px;
            box-sizing: border-box;
        }
        .container {
            display: block;
            width: 825px;
            max-width: 100%;
            margin: 0 auto;
            padding: 48px 50px;
            box-sizing: border-box;
        }
        .setting select,
        .setting input[type="date"] {
            width: 190px;
            height: 46px;
            padding: 0 14px;
            border: 1px solid #d7dee8;
            border-radius: 8px;
            background: #f8fafc;
            color: #1f2937;
            font: inherit;
            font-size: 16px;
            outline: none;
            box-sizing: border-box;
            transition: border-color .2s ease, box-shadow .2s ease, background .2s ease;
        }
        .setting select { cursor: pointer; }
        .setting select:hover,
        .setting input[type="date"]:hover { border-color: #9fb4cc; background: #fff; }
        .setting select:focus,
        .setting input[type="date"]:focus {
            border-color: #1f5f9f;
            background: #fff;
            box-shadow: 0 0 0 3px rgba(31, 95, 159, .12);
        }
        .process-pair {
            display: grid;
            grid-template-columns: 350px 220px;
            justify-content: center;
            align-items: center;
            column-gap: 24px;
            margin: 14px 0 20px;
        }
        .process-pair > .btn,
        .process-pair > button {
            width: 350px !important;
            margin: 0 !important;
        }
        .process-pair > .setting {
            width: 220px !important;
            margin: 0 !important;
            text-align: left;
        }
        .process-pair > .setting label {
            display: block;
            margin: 0 0 7px;
            font-size: 14px;
            line-height: 1.2;
            white-space: nowrap;
        }
        .process-pair > .setting select,
        .process-pair > .setting input[type="date"] { width: 190px; }

        @media (max-width: 700px) {
            body { padding: 20px 12px; }
            .container { padding: 30px 20px; }
            .process-pair {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .process-pair > .btn,
            .process-pair > button { width: 100% !important; }
            .process-pair > .setting { width: 100% !important; text-align: center; }
            .process-pair > .setting label { white-space: normal; }
        }
    </style>
'''
    html = html.replace('</head>', design_css + '\n</head>')

    layout_js = '''
<script>
window.addEventListener("DOMContentLoaded", function () {
    function directChildren(section, selector) {
        return Array.from(section.children).filter(el => el.matches(selector));
    }

    function makePair(button, setting) {
        if (!button || !setting || button.closest(".process-pair") || setting.closest(".process-pair")) return;
        const row = document.createElement("div");
        row.className = "process-pair";
        button.parentNode.insertBefore(row, button);
        row.appendChild(button);
        row.appendChild(setting);
    }

    const dial = document.getElementById("dialSection");
    if (dial) {
        const settings = directChildren(dial, ".setting");
        makePair(dial.querySelector(":scope > .btn-1"), settings[0]);
        makePair(dial.querySelector(":scope > .btn-3"), settings[1]);
    }

    const operations = document.getElementById("operationsSection");
    if (operations) {
        const settings = directChildren(operations, ".setting");
        makePair(operations.querySelector(":scope > .btn-4"), settings[0]);
    }

    const negative = document.getElementById("negativeSection");
    if (negative) {
        const settings = directChildren(negative, ".setting");
        const buttons = directChildren(negative, "button");
        makePair(buttons[0], settings[0]);
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
      .then(data => {
          result.style.color = "green";
          result.innerText = "✅ " + data.message;
      })
      .catch(error => {
          result.style.color = "red";
          result.innerText = "❌ " + error.message;
      });
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
        return jsonify({
            "status": "busy",
            "message": "Зараз уже виконується інший процес Asteril. Дочекайтеся його завершення.",
        }), 409

    try:
        result = run_order_count_report()
        return jsonify({
            "status": "success",
            "message": f"Звіт оновлено за {result['date']}. Записано статусів: {result['statuses']}.",
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
    finally:
        legacy.process_lock.release()
