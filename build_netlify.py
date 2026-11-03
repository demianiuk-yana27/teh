from pathlib import Path

p = Path('netlify/index.html')
if not p.exists():
    raise SystemExit('netlify/index.html is missing')

s = p.read_text(encoding='utf-8')
required = ['id="scripts"','id="techfaq"','id="ktv"','id="reviews"','id="dorobky"','id="ordercount"','id="negative-reviews"','id="negative-analytics"']
missing = [marker for marker in required if marker not in s]
if missing:
    raise SystemExit('Missing required sections: ' + ', '.join(missing))

# Database navigation: correspondence scripts, call scripts and refusal handling.
s = s.replace('data-view="scripts">💬 Скрипти</div>', 'data-view="scripts">💬 Скрипти для переписок</div><div class="sub" data-view="call-scripts">☎️ Скрипти для дзвінка</div><div class="sub" data-view="refusal-work">🚫 Робота з відмовою</div>', 1)
# Training materials: add the interactive Boxes subsection.
s = s.replace('data-view="training">📖 Навчальні матеріали</div>', 'data-view="training">📖 Навчальні матеріали</div><div class="sub training-child" data-view="boxes">↳ 📦 Коробки</div>', 1)

# Restore the rich correspondence Scripts view deterministically.
start = s.index('<section class="view" id="scripts">')
end = s.index('</section>', start) + len('</section>')
scripts_section = '''<section class="view" id="scripts">
<div class="pagehead"><div class="pageicon">💬</div><div><h2>Скрипти для переписок</h2><p>Усі скрипти з робочої таблиці «Влад».</p></div></div>
<div class="script-search-wrap"><input id="scriptSearch" class="faq-search" placeholder="Пошук по назві або тексту скрипта..."><span class="script-total">Усього: <b id="scriptTotal">0</b></span></div>
<div class="scripts-layout"><aside class="scripts-folders"><h3>Розділи</h3><div id="scriptFolders"></div></aside><div class="scripts-content"><div class="scripts-content-head"><h3 id="scriptCategoryTitle">Скрипти</h3><p id="scriptCategoryMeta"></p></div><div id="scriptCards"></div></div></div>
</section>'''
s = s[:start] + scripts_section + s[end:]

call_section = '''<section class="view" id="call-scripts">
<div class="pagehead"><div class="pageicon">☎️</div><div><h2>Скрипти для дзвінка</h2><p>Скрипт дзвінка з робочої таблиці, вкладка «Скрипт».</p></div></div>
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
insert_at = s.index('</section>', s.index('<section class="view" id="scripts">')) + len('</section>')
s = s[:insert_at] + call_section + refusal_section + boxes_section + s[insert_at:]

css = '''<style>
.script-search-wrap{display:flex;align-items:center;gap:14px;margin-bottom:18px}.script-search-wrap .faq-search{flex:1}.script-total{white-space:nowrap;color:#607896}.scripts-layout{display:grid;grid-template-columns:285px minmax(0,1fr);gap:18px}.scripts-folders,.scripts-content{background:#fff;border:1px solid #dce6f3;border-radius:16px;box-shadow:0 8px 24px #17385e0a}.scripts-folders{padding:18px;height:max-content}.scripts-folders h3{margin:3px 8px 12px}.script-folder{width:100%;border:0;background:transparent;border-radius:9px;padding:10px 11px;display:flex;justify-content:space-between;gap:10px;text-align:left;color:#203b5d;cursor:pointer;font:inherit}.script-folder.selected{background:#e6efff;color:#075de7;font-weight:700}.scripts-content{padding:20px}.scripts-content-head{border-bottom:1px solid #dce6f3;margin:-20px -20px 18px;padding:18px 20px}.scripts-content-head h3{margin:0 0 4px;font-size:22px}.scripts-content-head p{margin:0;color:#7184a2}.script-card{border:1px solid #d6e2f1;border-radius:13px;margin-bottom:14px;overflow:hidden}.script-card-head{display:flex;align-items:center;gap:10px;background:#f2f7ff;padding:12px 14px}.script-card-head strong{flex:1}.script-num{background:#dceaff;color:#0861df;border-radius:8px;padding:5px 7px;font-weight:800}.script-text{padding:15px 17px;line-height:1.65}.script-category-label{padding:10px 17px 0;color:#7184a2;font-size:12px;font-weight:700}.script-copy{float:none;margin-left:auto}.call-row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:14px}.call-cell{position:relative;background:#fff;border:1px solid #dce6f3;border-radius:14px;padding:17px 17px 52px;box-shadow:0 6px 18px #17385e08;min-width:0}.call-cell-text{white-space:pre-line;line-height:1.6;overflow-wrap:anywhere}.call-copy{position:absolute;right:14px;bottom:12px;float:none}.call-row:has(.call-cell:only-child){grid-template-columns:1fr}.call-section{grid-template-columns:1fr}.call-section .call-cell{background:#eaf2ff;border-color:#c9dbf7;padding-bottom:17px;font-size:18px;font-weight:800}.call-section .call-copy{display:none}@media(max-width:900px){.scripts-layout{grid-template-columns:1fr}.scripts-folders{display:block}.script-search-wrap{align-items:stretch;flex-direction:column}.script-total{padding-left:3px}.call-row{grid-template-columns:1fr}}
</style>'''
s = s.replace('</head>', css + '</head>', 1)

loaders = '<script src="scripts-data-1.js"></script><script src="scripts-data-2.js"></script><script src="scripts-data-3.js"></script><script src="scripts-ui.js"></script><script src="call-scripts-data.js"></script><script src="call-scripts-ui.js"></script><script src="refusal-data.js"></script><script src="refusal-ui.js"></script><script src="boxes-ui.js"></script>'
pos = s.rfind('<script>')
if pos < 0:
    raise SystemExit('Main frontend script not found')
s = s[:pos] + loaders + s[pos:]

p.write_text(s, encoding='utf-8')
print('Cloudflare frontend validated; scripts, refusal-work and boxes training views are ready.')
