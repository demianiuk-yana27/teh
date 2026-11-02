from pathlib import Path

p = Path('netlify/index.html')
if not p.exists():
    raise SystemExit('netlify/index.html is missing')

s = p.read_text(encoding='utf-8')
required = ['id="scripts"','id="techfaq"','id="ktv"','id="reviews"','id="dorobky"','id="ordercount"','id="negative-reviews"','id="negative-analytics"']
missing = [marker for marker in required if marker not in s]
if missing:
    raise SystemExit('Missing required sections: ' + ', '.join(missing))

# The FAQ redesign accidentally replaced the rich Scripts view with a placeholder.
# Restore it deterministically at build time while keeping the source page easy to edit.
start = s.index('<section class="view" id="scripts">')
end = s.index('</section>', start) + len('</section>')
scripts_section = '''<section class="view" id="scripts">
<div class="pagehead"><div class="pageicon">💬</div><div><h2>База знань: Скрипти</h2><p>Усі скрипти з робочої таблиці «Влад».</p></div></div>
<div class="script-search-wrap"><input id="scriptSearch" class="faq-search" placeholder="Пошук по назві або тексту скрипта..."><span class="script-total">Усього: <b id="scriptTotal">0</b></span></div>
<div class="scripts-layout"><aside class="scripts-folders"><h3>Розділи</h3><div id="scriptFolders"></div></aside><div class="scripts-content"><div class="scripts-content-head"><h3 id="scriptCategoryTitle">Скрипти</h3><p id="scriptCategoryMeta"></p></div><div id="scriptCards"></div></div></div>
</section>'''
s = s[:start] + scripts_section + s[end:]

css = '''<style>
.script-search-wrap{display:flex;align-items:center;gap:14px;margin-bottom:18px}.script-search-wrap .faq-search{flex:1}.script-total{white-space:nowrap;color:#607896}.scripts-layout{display:grid;grid-template-columns:285px minmax(0,1fr);gap:18px}.scripts-folders,.scripts-content{background:#fff;border:1px solid #dce6f3;border-radius:16px;box-shadow:0 8px 24px #17385e0a}.scripts-folders{padding:18px;height:max-content}.scripts-folders h3{margin:3px 8px 12px}.script-folder{width:100%;border:0;background:transparent;border-radius:9px;padding:10px 11px;display:flex;justify-content:space-between;gap:10px;text-align:left;color:#203b5d;cursor:pointer;font:inherit}.script-folder.selected{background:#e6efff;color:#075de7;font-weight:700}.scripts-content{padding:20px}.scripts-content-head{border-bottom:1px solid #dce6f3;margin:-20px -20px 18px;padding:18px 20px}.scripts-content-head h3{margin:0 0 4px;font-size:22px}.scripts-content-head p{margin:0;color:#7184a2}.script-card{border:1px solid #d6e2f1;border-radius:13px;margin-bottom:14px;overflow:hidden}.script-card-head{display:flex;align-items:center;gap:10px;background:#f2f7ff;padding:12px 14px}.script-card-head strong{flex:1}.script-num{background:#dceaff;color:#0861df;border-radius:8px;padding:5px 7px;font-weight:800}.script-text{padding:15px 17px;line-height:1.65}.script-category-label{padding:10px 17px 0;color:#7184a2;font-size:12px;font-weight:700}.script-copy{float:none;margin-left:auto}@media(max-width:900px){.scripts-layout{grid-template-columns:1fr}.scripts-folders{display:block}.script-search-wrap{align-items:stretch;flex-direction:column}.script-total{padding-left:3px}}
</style>'''
s = s.replace('</head>', css + '</head>', 1)

loaders = '<script src="scripts-data-1.js"></script><script src="scripts-data-2.js"></script><script src="scripts-data-3.js"></script><script src="scripts-ui.js"></script>'
pos = s.rfind('<script>')
if pos < 0:
    raise SystemExit('Main frontend script not found')
s = s[:pos] + loaders + s[pos:]

p.write_text(s, encoding='utf-8')
print('Netlify frontend validated and Scripts view restored successfully.')
