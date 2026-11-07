from pathlib import Path

p = Path('netlify/index.html')
if not p.exists():
    raise SystemExit('netlify/index.html is missing')

s = p.read_text(encoding='utf-8')
required = ['id="scripts"','id="techfaq"','id="ktv"','id="reviews"','id="dorobky"','id="ordercount"','id="negative-reviews"','id="negative-analytics"']
missing = [marker for marker in required if marker not in s]
if missing:
    raise SystemExit('Missing required sections: ' + ', '.join(missing))

# Site branding.
s = s.replace('<title>Asteril Automation</title>', '<title>Технічний відділ</title>', 1)
s = s.replace('<h1>Asteril Automation</h1>', '<h1>Технічний відділ</h1>', 1)

# Shared manager task board navigation.
s = s.replace('<div class="section-label">Відділи</div>', '<div class="section-label">Відділи</div><div class="navitem" data-view="task-board">📋 Дошка задач</div><div class="navitem" data-view="quick-requests">🐿️ Швидка подача запитів</div>', 1)

# Retire the unused standalone response templates page and menu entry.
s = s.replace('<div class="sub" data-view="templates">▤ Шаблони відповідей</div>', '', 1)
s = s.replace('<section class="view" id="templates"><div class="empty"><h2>Шаблони відповідей</h2></div></section>', '', 1)

# Home dashboard: direct shortcuts to the existing sections (no duplicate workflows).
home_dashboard = """<section class="view" id="home">
<div class="pagehead"><div class="pageicon">🏠</div><div><h2>Головна</h2><p>Усі потрібні інструменти та інструкції — в одному місці.</p></div></div>
<div class="home-welcome"><div class="home-welcome-icon">✨</div><div><h3>З чого почнемо?</h3><p>Оберіть потрібний напрямок — і одразу переходьте до роботи.</p></div></div>
<div class="home-quick-group"><div class="home-group-heading"><h3>📚 База знань</h3><p>Підказки та готові інструкції</p></div><div class="home-quick-grid">
<button class="home-shortcut" data-target-view="scripts"><span class="home-shortcut-icon">💬</span><strong>Скрипти для переписок</strong><small>Відповіді та формулювання для клієнтів</small></button>
<button class="home-shortcut" data-target-view="call-scripts"><span class="home-shortcut-icon">☎️</span><strong>Скрипти для дзвінка</strong><small>Готові сценарії розмов</small></button>
<button class="home-shortcut" data-target-view="refusal-work"><span class="home-shortcut-icon">🚫</span><strong>Робота з відмовою</strong><small>Аргументи та заперечення</small></button>
<button class="home-shortcut" data-target-view="techfaq"><span class="home-shortcut-icon">❔</span><strong>Питання про техвідділ</strong><small>Поширені питання та відповіді</small></button>
</div></div>
<div class="home-quick-group"><div class="home-group-heading"><h3>🎓 Навчання</h3><p>Матеріали для роботи та стажування</p></div><div class="home-quick-grid">
<button class="home-shortcut" data-target-view="training"><span class="home-shortcut-icon">📖</span><strong>Навчальні матеріали</strong><small>Інструкції, фото та відео</small></button>
<button class="home-shortcut" data-target-view="boxes"><span class="home-shortcut-icon">📦</span><strong>Коробки</strong><small>Підбір коробок і пакування</small></button>
<button class="home-shortcut" data-target-view="order-rules"><span class="home-shortcut-icon">🔄</span><strong>Скасування й об’єднання</strong><small>Правила роботи із замовленнями</small></button>
<button class="home-shortcut" data-target-view="call-training"><span class="home-shortcut-icon">📞</span><strong>Стажування на продзвін</strong><small>Відгуки, КТВ, Бурундуки + Розетка</small></button>

</div></div>
<div class="home-quick-group"><div class="home-group-heading"><h3>📞 Продзвін</h3><p>Робочі процеси для команди</p></div><div class="home-quick-grid">
<button class="home-shortcut" data-target-view="ktv"><span class="home-shortcut-icon">📦</span><strong>КТВ</strong><small>Підготовка вивантаження</small></button>
<button class="home-shortcut" data-target-view="reviews"><span class="home-shortcut-icon">⭐</span><strong>Відгуки</strong><small>Робота з відгуками покупців</small></button>
</div></div>
<div class="home-quick-group"><div class="home-group-heading"><h3>👥 Операційні менеджери</h3><p>Щоденні задачі та звітність</p></div><div class="home-quick-grid">
<button class="home-shortcut" data-target-view="dorobky"><span class="home-shortcut-icon">🛠️</span><strong>Доробки</strong><small>Операційне вивантаження</small></button>
<button class="home-shortcut" data-target-view="ordercount"><span class="home-shortcut-icon">📊</span><strong>Звіт за замовленнями</strong><small>Кількість замовлень</small></button>
</div></div>
<div class="home-quick-group"><div class="home-group-heading"><h3>⭐ Негативні відгуки</h3><p>Вивантаження та аналітика</p></div><div class="home-quick-grid">
<button class="home-shortcut" data-target-view="negative-reviews"><span class="home-shortcut-icon">⭐</span><strong>Вивантаження негативних відгуків</strong><small>Відгуки для опрацювання</small></button>
<button class="home-shortcut" data-target-view="negative-analytics"><span class="home-shortcut-icon">📈</span><strong>Аналітика негативних відгуків</strong><small>Показники роботи з відгуками</small></button>
</div></div>
<div class="home-quick-group"><div class="home-group-heading"><h3>📋 Робочі інструменти</h3><p>Планування та контроль задач</p></div><div class="home-quick-grid">
<button class="home-shortcut" data-target-view="task-board"><span class="home-shortcut-icon">📋</span><strong>Дошка задач</strong><small>Задачі, терміни та прогрес</small></button>\n<button class="home-shortcut" data-target-view="quick-requests"><span class="home-shortcut-icon">🐿️</span><strong>Швидка подача запитів</strong><small>Бурундуки та зміни з ТТН</small></button>
</div></div>
</section>"""
s = s.replace('<section class="view active" id="home"><div class="empty"><h2>Головна</h2><p>Оберіть потрібний розділ у меню.</p></div></section>', home_dashboard.replace('class="view" id="home"', 'class="view active" id="home"'), 1)

# Product catalog and FAQ feature temporarily disabled; source and D1 data retained.

# Boss dashboard: separate section; the API enforces the boss role server-side.
s = s.replace('<div class="section-label">Відділи</div>', '<div class="section-label">Відділи</div><div class="navitem" data-view="boss-dashboard">📊 Дашборд керівника</div>', 1)
s = s.replace('</main>', '<section class="view" id="boss-dashboard"><div class="pagehead"><div class="pageicon">📊</div><div><h2>Дашборд керівника</h2><p>Статистика, історія вигрузок та виконані задачі.</p></div></div><div id="bossDashboard"></div></section></main>', 1)

# TTN workflow is isolated under Operational Managers.
s = s.replace('data-view="dorobky">• Доробки</div>', 'data-view="dorobky">• Доробки</div><div class="sub" data-view="ttn">• Зміни з ТТН</div>', 1)
s = s.replace('</main>', '<section class="view" id="ttn"><div class="pagehead"><div class="pageicon">📦</div><div><h2>Зміни з ТТН</h2><p>Неопрацьовані запити, листи та передача Богдану.</p></div></div><div id="ttnApp"></div></section></main>', 1)

# Database navigation: correspondence scripts, call scripts and refusal handling.
s = s.replace('data-view="scripts">💬 Скрипти</div>', 'data-view="scripts">💬 Скрипти для переписок</div><div class="sub" data-view="call-scripts">☎️ Скрипти для дзвінка</div><div class="sub" data-view="refusal-work">🚫 Робота з відмовою</div>', 1)
# Training materials subsections.
s = s.replace('data-view="training">📖 Навчальні матеріали</div>', 'data-view="training">📖 Навчальні матеріали</div><div class="sub training-child" data-view="boxes">↳ 📦 Коробки</div><div class="sub training-child" data-view="order-rules">↳ 🔄 Скасування та об’єднання замовлень</div><div class="sub training-child" data-view="call-training">↳ 📞 Стажування на продзвін</div>', 1)

# Restore the rich correspondence Scripts view deterministically.
start = s.index('<section class="view" id="scripts">')
end = s.index('</section>', start) + len('</section>')
scripts_section = '''<section class="view" id="scripts">
<div class="pagehead"><div class="pageicon">💬</div><div><h2>Скрипти для переписок</h2><p>Готові шаблони для спілкування з клієнтом у переписці.</p></div></div>
<div class="script-search-wrap"><input id="scriptSearch" class="faq-search" placeholder="Пошук по назві або тексту скрипта..."><span class="script-total">Усього: <b id="scriptTotal">0</b></span></div>
<div class="scripts-layout"><aside class="scripts-folders"><h3>Розділи</h3><div id="scriptFolders"></div></aside><div class="scripts-content"><div class="scripts-content-head"><h3 id="scriptCategoryTitle">Скрипти</h3><p id="scriptCategoryMeta"></p></div><div id="scriptCards"></div></div></div>
</section>'''
s = s[:start] + scripts_section + s[end:]

call_section = '''<section class="view" id="call-scripts">
<div class="pagehead"><div class="pageicon">☎️</div><div><h2>Скрипти для дзвінка</h2><p>Структура розмови з клієнтом під час телефонного дзвінка.</p></div></div>
<div class="script-search-wrap"><input id="callScriptSearch" class="faq-search" placeholder="Пошук по скрипту, товару, артикулу або фразі..."><span class="script-total">Знайдено блоків: <b id="callScriptTotal">0</b></span></div>
<div id="callScriptList"></div>
</section>'''
refusal_section = '''<section class="view" id="refusal-work">
<div class="pagehead"><div class="pageicon">🚫</div><div><h2>Робота з відмовою</h2><p>Структура опрацювання відмов клієнтів, причини та готові формулювання.</p></div></div>
<div id="refusalContent"></div>
</section>'''
boxes_section = '''<section class="view" id="boxes">
<div class="pagehead"><div class="pageicon">📦</div><div><h2>Навчальні матеріали — Коробки</h2><p>Інтерактивна інструкція з підбору коробки, габаритів та пакування.</p></div></div>
<div id="boxesApp"></div>
</section>'''
order_rules_section = '''<section class="view" id="order-rules">
<div class="pagehead"><div class="pageicon">🔄</div><div><h2>Скасування та об’єднання замовлень</h2><p>Правила роботи з кількома невідправленими замовленнями одного клієнта.</p></div></div>
<div id="orderRulesApp"></div>
</section>'''
call_training_section = '''<section class="view" id="call-training">
<div class="pagehead"><div class="pageicon">📞</div><div><h2>Стажування на продзвін</h2><p>Покрокова програма для нових менеджерів: Відгуки, КТВ, Бурундуки + Розетка.</p></div></div>
<div id="callTrainingApp"></div>
</section>'''
quick_requests_section = '''<section class="view" id="quick-requests"><div class="pagehead"><div class="pageicon">🐿️</div><div><h2>Швидка подача запитів</h2><p>Бурундуки та зміни з ТТН — прямо на сайті.</p></div></div><div id="quickRequestsApp"></div></section>'''
task_board_section = '''<section class="view" id="task-board">
<div class="pagehead"><div class="pageicon">📋</div><div><h2>Дошка задач</h2><p>Спільні задачі менеджерів, дедлайни та архів виконаного.</p></div></div>
<div id="taskBoardApp"></div>
</section>'''
s = s.replace('</main>', task_board_section + call_training_section + quick_requests_section + '</main>', 1)

# Rich training materials editor lives inside the existing training view.
s = s.replace('<div class="empty"><h2>Навчальні матеріали</h2></div>', '<div id="trainingMaterialsApp"></div>', 1)

insert_at = s.index('</section>', s.index('<section class="view" id="scripts">')) + len('</section>')
s = s[:insert_at] + call_section + refusal_section + boxes_section + order_rules_section + s[insert_at:]

home_css = """<style>
#home{max-width:1220px}.home-welcome{display:flex;align-items:center;gap:18px;background:linear-gradient(115deg,#e8f1ff,#f8fbff);border:1px solid #d5e4fa;border-radius:18px;padding:24px 28px;margin-bottom:28px}.home-welcome-icon{display:grid;place-items:center;flex:0 0 56px;height:56px;border-radius:15px;background:#fff;font-size:28px}.home-welcome h3{margin:0 0 6px;font-size:22px;color:#173253}.home-welcome p{margin:0;color:#637b9c;line-height:1.5}.home-quick-group{margin:0 0 29px}.home-group-heading{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin:0 0 14px}.home-group-heading h3{margin:0;font-size:20px;color:#193456}.home-group-heading p{margin:0;color:#7185a0;font-size:13px}.home-quick-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.home-shortcut{display:flex;flex-direction:column;align-items:flex-start;gap:9px;text-align:left;min-height:150px;padding:20px;border:1px solid #dce6f3;background:#fff;border-radius:16px;cursor:pointer;color:#1b3454;font:inherit;box-shadow:0 6px 20px #17385e09;transition:border-color .15s,transform .15s,box-shadow .15s}.home-shortcut:hover,.home-shortcut:focus-visible{border-color:#1769f6;transform:translateY(-2px);box-shadow:0 10px 24px #1769f61a;outline:none}.home-shortcut-icon{display:grid;place-items:center;background:#eef4ff;border-radius:12px;width:43px;height:43px;font-size:23px}.home-shortcut strong{font-size:16px}.home-shortcut small{color:#637b9c;font-size:13px;line-height:1.5}@media(max-width:1050px){.home-quick-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.home-quick-grid{grid-template-columns:1fr}.home-welcome{padding:18px}.home-group-heading{display:block}.home-group-heading p{margin-top:5px}}
</style>"""
s = s.replace('</head>', home_css + '</head>', 1)
home_navigation = """<script>
document.addEventListener('click',function(event){
 const shortcut=event.target.closest('[data-target-view]');
 if(!shortcut)return;
 const target=shortcut.dataset.targetView;
 const sidebar=document.querySelector('aside [data-view="'+target+'"]');
 if(!sidebar||!document.getElementById(target))return;
 sidebar.click();
 window.scrollTo({top:0,behavior:'smooth'});
});
</script>"""
s = s.replace('</body>', home_navigation + '</body>', 1)

quick_requests_css = '''<style>
#quickRequestsApp{max-width:850px}.qr-tabs{display:flex;gap:12px;margin-bottom:18px}.qr-tabs button{border:1px solid #d5e2f5;background:#fff;border-radius:13px;padding:15px 22px;font-size:16px;font-weight:750;color:#1a3455;cursor:pointer}.qr-tabs button.selected{background:#e9f2ff;border:2px solid #1769f6;color:#1258c5;padding:14px 21px}.qr-panel{background:#fff;border:1px solid #dbe6f5;border-radius:18px;padding:26px;box-shadow:0 8px 24px #17385e0a}.qr-grid{display:block}.qr-full{grid-column:1/-1}.qr-grid label{font-weight:700;color:#1c3455;font-size:14px;display:block;margin:15px 0 7px}.qr-grid input,.qr-grid select,.qr-grid textarea{display:block;width:100%;box-sizing:border-box;border:1px solid #cbd9eb;border-radius:10px;padding:12px;font:inherit;background:#fff;color:#173253}.qr-grid textarea{resize:vertical}.qr-note{margin:0;background:#eef5ff;border-radius:10px;padding:13px;color:#506b91}.qr-remember{display:flex;align-items:center;gap:8px;margin-top:18px;font-size:14px;color:#526d8e}.qr-actions{display:flex;align-items:center;gap:15px;margin-top:20px;flex-wrap:wrap}.qr-submit{background:#1769f6;border:0;border-radius:11px;color:#fff;padding:13px 22px;font-weight:800;cursor:pointer}.qr-submit:disabled{opacity:.55;cursor:wait}#qr-status{color:#526d8e;line-height:1.5}@media(max-width:650px){.qr-grid{grid-template-columns:1fr}.qr-panel{padding:16px}.qr-tabs button{flex:1;padding:12px 8px;font-size:14px}}
</style>'''
s = s.replace('</head>', quick_requests_css + '</head>', 1)
css = '''<style>
#trainingMaterialsApp{max-width:1080px}.tm-head,.tm-actions,.tm-add{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:18px}.tm-head{justify-content:space-between}.tm-head p{color:#607896}.tm-actions button,.tm-head button,.tm-card button,.tm-add button,.tm-blockbar button{border:1px solid #cad9ec;background:#edf3fc;color:#24466e;border-radius:9px;padding:9px 12px;cursor:pointer;font-weight:700}.tm-actions .tm-primary,.tm-head .tm-primary{background:#1769f6;color:white;border-color:#1769f6}.tm-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:16px}.tm-card,.tm-article,.tm-form{background:#fff;border:1px solid #dce6f3;border-radius:16px;padding:22px;box-shadow:0 8px 24px #17385e0a}.tm-card h3{margin:8px 0}.tm-card p,.tm-summary{color:#607896;line-height:1.6}.tm-status{font-size:12px;color:#59708d}.tm-article{max-width:860px;line-height:1.7}.tm-article h2{font-size:28px}.tm-article figure{margin:24px 0}.tm-article img,.tm-article video{display:block;max-width:100%;max-height:680px;border-radius:12px}.tm-article figcaption{color:#7184a2;font-size:13px;margin-top:7px}.tm-prose{white-space:normal;overflow-wrap:anywhere}.tm-video{position:relative;padding-bottom:56.25%;height:0}.tm-video iframe{position:absolute;inset:0;width:100%;height:100%;border:0;border-radius:12px}.tm-draft{color:#9a6418}.tm-form label,.tm-block label{display:block;font-weight:700;margin:12px 0}.tm-form input:not([type=file]),.tm-form textarea{display:block;width:100%;font:inherit;border:1px solid #cbd9eb;border-radius:10px;padding:11px;margin-top:6px}.tm-block{border:1px solid #dce6f3;border-radius:13px;padding:16px;margin:12px 0;background:#f8fbff}.tm-blockbar{display:flex;align-items:center;justify-content:space-between;gap:8px}.tm-blockbar button{padding:5px 10px;margin-left:4px}.tm-add{margin:16px 0}.tm-add span{width:100%;font-weight:700}.tm-upload{padding:10px 0}.tm-upload small{display:block;color:#607896;margin-top:5px}.tm-notice:not(:empty){background:#eaf2ff;color:#1b528e;border-radius:10px;padding:12px;margin-bottom:15px}.tm-error{color:#b9323b}
.script-search-wrap{display:flex;align-items:center;gap:14px;margin-bottom:18px}.script-search-wrap .faq-search{flex:1}.script-total{white-space:nowrap;color:#607896}.scripts-layout{display:grid;grid-template-columns:285px minmax(0,1fr);gap:18px}.scripts-folders,.scripts-content{background:#fff;border:1px solid #dce6f3;border-radius:16px;box-shadow:0 8px 24px #17385e0a}.scripts-folders{padding:18px;height:max-content}.scripts-folders h3{margin:3px 8px 12px}.script-folder{width:100%;border:0;background:transparent;border-radius:9px;padding:10px 11px;display:flex;justify-content:space-between;gap:10px;text-align:left;color:#203b5d;cursor:pointer;font:inherit}.script-folder.selected{background:#e6efff;color:#075de7;font-weight:700}.scripts-content{padding:20px}.scripts-content-head{border-bottom:1px solid #dce6f3;margin:-20px -20px 18px;padding:18px 20px}.scripts-content-head h3{margin:0 0 4px;font-size:22px}.scripts-content-head p{margin:0;color:#7184a2}.script-card{border:1px solid #d6e2f1;border-radius:13px;margin-bottom:14px;overflow:hidden}.script-card-head{display:flex;align-items:center;gap:10px;background:#f2f7ff;padding:12px 14px}.script-card-head strong{flex:1}.script-num{background:#dceaff;color:#0861df;border-radius:8px;padding:5px 7px;font-weight:800}.script-text{padding:15px 17px;line-height:1.65}.script-category-label{padding:10px 17px 0;color:#7184a2;font-size:12px;font-weight:700}.script-copy{float:none;margin-left:auto}.call-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:14px}.call-cell{position:relative;background:#fff;border:1px solid #dce6f3;border-radius:14px;padding:17px 17px 52px;box-shadow:0 6px 18px #17385e08;min-width:0}.call-cell-text{white-space:pre-line;line-height:1.6;overflow-wrap:anywhere}.call-copy{position:absolute;right:14px;bottom:12px;float:none;margin-left:auto}.call-row:has(.call-cell:only-child){grid-template-columns:1fr}.call-section{grid-template-columns:1fr}.call-section .call-cell{background:#eaf2ff;border-color:#c9dbf7;padding-bottom:17px;font-size:18px;font-weight:800}.call-section .call-copy{display:none}@media(max-width:900px){.scripts-layout{grid-template-columns:1fr}.scripts-folders{display:block}.script-search-wrap{align-items:stretch;flex-direction:column}.script-total{padding-left:3px}.call-row{grid-template-columns:1fr}}
</style>'''
s = s.replace('</head>', css + '</head>', 1)

css += '''<style>
#callTrainingApp{max-width:1100px}.ct-intro{display:flex;align-items:center;gap:18px;background:linear-gradient(120deg,#e8f1ff,#f8fbff);border:1px solid #d4e3f8;border-radius:18px;padding:22px 26px;margin-bottom:22px}.ct-intro-icon{font-size:34px;background:white;border-radius:14px;padding:12px}.ct-intro h3{margin:0 0 6px;font-size:21px}.ct-intro p{margin:0;color:#5f7594;line-height:1.5}.ct-tabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:20px}.ct-tabs button{text-align:left;display:flex;flex-direction:column;gap:8px;padding:19px;border:1px solid #dce6f3;border-radius:16px;background:white;cursor:pointer;color:#203858;font:inherit;box-shadow:0 5px 16px #17385e08}.ct-tabs button>span{font-size:25px}.ct-tabs strong{font-size:17px}.ct-tabs small{color:#607896;line-height:1.5;font-size:12px}.ct-tabs button.selected{border:2px solid #1769f6;background:#edf4ff;padding:18px}.ct-panel{background:white;border:1px solid #dce6f3;border-radius:18px;padding:26px;box-shadow:0 8px 24px #17385e0a}.ct-panel-heading{display:flex;align-items:center;gap:15px;padding-bottom:18px;border-bottom:1px solid #e4ebf5}.ct-panel-heading>span{font-size:29px}.ct-panel-heading h3{margin:0 0 5px;font-size:24px}.ct-panel-heading p{margin:0;color:#667d9c}.ct-steps{display:grid;gap:13px;margin-top:20px}.ct-step{display:flex;gap:16px;background:#f7faff;border:1px solid #e5edf8;border-radius:13px;padding:18px}.ct-number{flex:0 0 37px;height:37px;display:grid;place-items:center;background:#e0ecff;border-radius:11px;color:#1260d6;font-weight:800}.ct-step-body{min-width:0;line-height:1.75;white-space:pre-line}.ct-step-body p{margin:0}.ct-step-body ul{margin:0;padding-left:19px}.ct-step-body li{margin-bottom:6px}.ct-next{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:23px}.ct-next button{border:1px solid #c8d9f0;background:#f4f8ff;border-radius:10px;padding:11px 16px;cursor:pointer;font-weight:750;color:#1c5596}.ct-next .ct-next-primary{background:#1769f6;color:#fff;border-color:#1769f6}@media(max-width:750px){.ct-tabs{grid-template-columns:1fr}.ct-panel{padding:16px}.ct-intro{padding:16px}.ct-step{padding:13px}}
</style>'''
s = s.replace('</head>', css + '</head>', 1)

css += '''<style>
.ct-import{background:#eef5ff;border:1px solid #cbdffc;border-radius:14px;padding:18px 20px;margin-bottom:20px}.ct-import strong{color:#174a8c}.ct-import p{color:#57708f;line-height:1.55;margin:8px 0}.ct-import input{display:block;max-width:100%;margin-top:12px}.ct-shot{margin:3px 0 14px 53px;background:#fff;border:1px solid #dbe7f5;border-radius:14px;padding:13px;max-width:850px}.ct-shot img{display:block;width:100%;height:auto;max-height:580px;object-fit:contain;border-radius:9px}.ct-shot figcaption{font-size:13px;color:#647c9c;margin-top:9px;text-align:center}@media(max-width:750px){.ct-shot{margin-left:0}}
</style>'''
s = s.replace('</head>', css + '</head>', 1)

loaders = '<script src="scripts-data-1.js"></script><script src="scripts-data-2.js"></script><script src="scripts-data-3.js"></script><script src="scripts-ui.js"></script><script src="call-scripts-data.js"></script><script src="call-scripts-ui.js"></script><script src="refusal-data.js"></script><script src="refusal-ui.js"></script><script src="boxes-ui.js"></script><script src="order-rules-ui.js"></script><script src="access-control.js?v=20261103-full-cat"></script><script src="task-board.js?v=3"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js" defer></script><script src="call-training-guide.js?v=1"></script><script src="call-training-ui.js?v=3"></script><script src="quick-requests.js?v=1"></script><script src="training-materials.js?v=6"></script>'
# Product catalog scripts intentionally not loaded while feature is disabled.
loaders += '<script src="ttn.js?v=2"></script><script src="boss-dashboard.js?v=2"></script>'
pos = s.rfind('<script>')
if pos < 0:
    raise SystemExit('Main frontend script not found')
s = s[:pos] + loaders + s[pos:]

p.write_text(s, encoding='utf-8')
print('Cloudflare frontend validated; training, database and role access views are ready.')