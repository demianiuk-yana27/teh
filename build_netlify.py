from pathlib import Path

p = Path('netlify/index.html')
s = p.read_text(encoding='utf-8')

start = s.index('<section class="view active" id="scripts">')
end = s.index('<section class="view" id="ktv">', start)
new_scripts = '''<section class="view active" id="scripts">
<div class="pagehead"><div class="pageicon">🗄️</div><div><h2>База знань: Скрипти</h2><p>Скрипти з робочої таблиці «Влад». Оберіть розділ і скопіюйте потрібну відповідь.</p></div></div>
<div class="chips" id="scriptChips"></div>
<div class="workspace"><div class="folders"><h3>Розділи</h3><div id="scriptFolders"></div></div><div class="content"><div class="contenthead"><div class="pageicon" style="width:48px;height:48px">▤</div><div><h3 id="scriptCategoryTitle">Скрипти</h3><p id="scriptCategoryMeta"></p></div></div><div class="cards" id="scriptCards"></div></div></div>
</section>
'''
s = s[:start] + new_scripts + s[end:]

loader = '''<script src="scripts-data-1.js"></script>\n<script src="scripts-data-2.js"></script>\n<script src="scripts-data-3.js"></script>\n'''
pos = s.rfind('<script>')
s = s[:pos] + loader + s[pos:]

marker = "const API='/api';const mainTimers={};const negativeTimers={};"
extra = r'''
let activeScriptCategory=0;
function esc(v){return String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]))}
function renderScriptNav(){
 const folders=document.getElementById('scriptFolders'),chips=document.getElementById('scriptChips');
 if(!folders||!window.SCRIPT_DATA)return;
 const total=SCRIPT_DATA.reduce((n,c)=>n+c.items.length,0);
 chips.innerHTML='<div class="chip active">Усі скрипти &nbsp; '+total+'</div>';
 folders.innerHTML=SCRIPT_DATA.map((c,i)=>'<div class="folder '+(i===activeScriptCategory?'active':'')+'" onclick="renderScriptCategory('+i+')"><span>▱ '+esc(c.category.replace(/^\\d+\\.\\s*/,''))+'</span><span>'+c.items.length+'</span></div>').join('');
 renderScriptCategory(activeScriptCategory);
}
function renderScriptCategory(i){
 activeScriptCategory=i; const c=SCRIPT_DATA[i]; if(!c)return;
 document.querySelectorAll('#scriptFolders .folder').forEach((x,n)=>x.classList.toggle('active',n===i));
 document.getElementById('scriptCategoryTitle').textContent=c.category;
 document.getElementById('scriptCategoryMeta').textContent=c.items.length+' готових відповідей';
 document.getElementById('scriptCards').innerHTML=c.items.map((x,n)=>'<div class="script"><div class="script-title"><span class="num">'+String(n+1).padStart(2,'0')+'</span><span>'+esc(x.title)+'</span><button class="copy" onclick="copyText(this)">▣ Скопіювати</button></div><div class="script-body">'+esc(x.text).replace(/\\n/g,'<br>')+'</div></div>').join('');
}
'''
s = s.replace(marker, marker + extra)
s = s.replace("document.getElementById('orderCheckUntil').value=iso(today);", "document.getElementById('orderCheckUntil').value=iso(today);renderScriptNav();")
p.write_text(s, encoding='utf-8')
