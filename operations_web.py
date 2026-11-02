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
