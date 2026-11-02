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
        .setting input[type="date"]:hover {
            border-color: #9fb4cc;
            background: #fff;
        }

        .setting select:focus,
        .setting input[type="date"]:focus {
            border-color: #1f5f9f;
            background: #fff;
            box-shadow: 0 0 0 3px rgba(31, 95, 159, .12);
        }

        /* На великих екранах: кнопка процесу ліворуч, його параметр праворуч. */
        @media (min-width: 701px) {
            #dialSection,
            #operationsSection,
            #negativeSection {
                text-align: center;
            }

            #dialSection .setting,
            #operationsSection .setting,
            #negativeSection .setting {
                margin: 0;
            }

            #dialSection .setting label,
            #operationsSection .setting label,
            #negativeSection .setting label {
                margin-bottom: 7px;
                font-size: 14px;
            }

            /* Продзвін: параметр КТВ стає праворуч від кнопки КТВ. */
            #dialSection > .setting:nth-of-type(1) {
                display: inline-flex;
                width: 260px;
                min-height: 76px;
                margin-left: 18px;
                vertical-align: middle;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }

            #dialSection > .btn-1 {
                display: inline-block;
                width: 350px;
                margin: 10px 0;
                vertical-align: middle;
            }

            /* Переносимо перший параметр візуально після кнопки за допомогою flex-like order. */
            #dialSection {
                font-size: 0;
            }
            #dialSection > * { font-size: 16px; }
            #dialSection > h3 { display: block; }
            #dialSection > .setting:nth-of-type(1) { position: relative; }
            #dialSection > .btn-1 { position: relative; }

            /* Дата відгуків + кнопка відгуків в один рядок. */
            #dialSection > .setting:nth-of-type(2),
            #dialSection > .btn-3 {
                display: inline-flex;
                vertical-align: middle;
            }
            #dialSection > .setting:nth-of-type(2) {
                width: 260px;
                min-height: 76px;
                margin-left: 18px;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }
            #dialSection > .btn-3 {
                width: 350px;
                height: 54px;
                align-items: center;
                justify-content: center;
            }

            /* Операційні: час поруч із кнопкою Доробок. */
            #operationsSection > .setting,
            #operationsSection > .btn-4 {
                display: inline-flex;
                vertical-align: middle;
            }
            #operationsSection > .setting {
                width: 260px;
                min-height: 76px;
                margin-left: 18px;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }
            #operationsSection > .btn-4 {
                width: 350px;
                height: 54px;
                align-items: center;
                justify-content: center;
            }

            /* Негативні: дата поруч із кнопкою вигрузки. */
            #negativeSection > .setting,
            #negativeSection > button:first-of-type {
                display: inline-flex;
                vertical-align: middle;
            }
            #negativeSection > .setting {
                width: 260px;
                min-height: 76px;
                margin-left: 18px;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }
            #negativeSection > button:first-of-type {
                width: 350px;
                height: 54px;
                align-items: center;
                justify-content: center;
            }
        }

        @media (max-width: 700px) {
            body { padding: 20px 12px; }
            .container { padding: 30px 20px; }
        }
    </style>
'''
    html = html.replace('</head>', design_css + '\n</head>')

    # CSS grid дає правильний порядок: кнопка процесу зліва, її параметр справа,
    # не змінюючи HTML та JS старих процесів.
    layout_js = '''
<script>
window.addEventListener("DOMContentLoaded", function () {
    if (window.innerWidth <= 700) return;

    function pair(sectionId, buttonSelector, settingSelector) {
        const section = document.getElementById(sectionId);
        if (!section) return;
        const button = section.querySelector(buttonSelector);
        const setting = section.querySelector(settingSelector);
        if (!button || !setting) return;
        const row = document.createElement("div");
        row.style.display = "flex";
        row.style.justifyContent = "center";
        row.style.alignItems = "center";
        row.style.gap = "18px";
        row.style.margin = "12px 0 18px";
        button.parentNode.insertBefore(row, button);
        row.appendChild(button);
        row.appendChild(setting);
    }

    pair("dialSection", ".btn-1", ".setting:nth-of-type(1)");
    pair("dialSection", ".btn-3", ".setting:nth-of-type(1)");
    pair("operationsSection", ".btn-4", ".setting:nth-of-type(1)");
    pair("negativeSection", "button", ".setting:nth-of-type(1)");
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
