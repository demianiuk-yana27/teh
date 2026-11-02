(()=>{
function esc(s){return String(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
const sectionRe=/(?:01|02|03|04)\s*[•]/;
const headingRe=/^(?:Привітання|📦 Наявність і відправка|🛡️ Подовжена гарантія|🚚 Звірка доставки та оплати|↳ |Товари для жінок|Товари для чоловіків|🧭 ПІДКАЗКИ МЕНЕДЖЕРУ|ТОВАР|ПРОПОЗИЦІЯ|КОЛИ ПОЦІКАВИЛИСЬ АБО ЗАПИТАЛИ ЦІНУ|🔀 ОБЕРІТЬ ОДИН ВАРІАНТ|📦 |🛠 |👔 |💇 |🔦 |⭐ |💰 |🎯 |🧾 |❌ |✅ |⚠️ |🔁 |💬 |🎁 )/;
function isSection(s){return sectionRe.test(s||'')}
function isHeading(s){s=String(s||'').trim();return !!s&&(headingRe.test(s)||(/^[А-ЯІЇЄҐ0-9][А-ЯІЇЄҐ0-9\s—–:|•()«»'’.,-]{4,}$/.test(s)&&s.length<120))}
function cleanTitle(s){return String(s||'').trim()}
function buildGroups(rows){
 const out=[];let section=null;let group=null;
 function addGroup(title){group={title:cleanTitle(title),left:[],right:[],rows:[]};out.push({type:'group',section,group});return group}
 rows.forEach(r=>{
  const l=cleanTitle(r.left),rr=cleanTitle(r.right);
  if(isSection(l)&&!rr){section=l;group=null;out.push({type:'section',title:l});return}
  if(l&&isHeading(l)&&(!rr||isHeading(rr))){
    const title=rr&&l!==rr?`${l} / ${rr}`:l;
    group=addGroup(title);group.rows.push(r.row);
    // For product/title rows keep the title as heading, not repeated in body.
    return;
  }
  if(!group)group=addGroup('Скрипт');
  group.rows.push(r.row);if(l)group.left.push(l);if(rr)group.right.push(rr);
 });return out
}
function copyBtn(text){return `<button class="copy call-copy" data-copy="${encodeURIComponent(text)}">▣ Скопіювати</button>`}
function renderGroup(x){const g=x.group;const left=g.left.join('\n\n'),right=g.right.join('\n\n');const hasBoth=left&&right;return `<article class="call-group"><div class="call-group-head"><strong>${esc(g.title)}</strong>${!hasBoth&&left?copyBtn(left):''}</div><div class="call-group-body${hasBoth?' call-two-col':''}">${left?`<div class="call-script-body">${hasBoth?'<div class="call-side-label">Для жінок</div>':''}<div class="call-text">${esc(left)}</div>${hasBoth?copyBtn(left):''}</div>`:''}${right?`<div class="call-script-body"><div class="call-side-label">Для чоловіків</div><div class="call-text">${esc(right)}</div>${copyBtn(right)}</div>`:''}</div></article>`}
function render(q=''){
 const root=document.getElementById('callScriptList');if(!root)return;const rows=window.CALL_SCRIPT_ROWS||[];q=q.toLowerCase().trim();let items=buildGroups(rows);
 if(q)items=items.filter(x=>x.type==='section'||((x.group.title+' '+x.group.left.join(' ')+' '+x.group.right.join(' ')).toLowerCase().includes(q)));
 // Hide section headings that have no matching groups after search.
 if(q)items=items.filter((x,i)=>x.type!=='section'||items.slice(i+1).some(y=>y.type==='group'&&y.section===x.title));
 const groups=items.filter(x=>x.type==='group');const total=document.getElementById('callScriptTotal');if(total)total.textContent=groups.length;
 root.innerHTML=items.map(x=>x.type==='section'?`<div class="call-section-title">${esc(x.title)}</div>`:renderGroup(x)).join('')||'<div class="empty">Нічого не знайдено.</div>';
 root.querySelectorAll('[data-copy]').forEach(btn=>btn.onclick=()=>{navigator.clipboard.writeText(decodeURIComponent(btn.dataset.copy));btn.textContent='✓ Скопійовано';setTimeout(()=>btn.textContent='▣ Скопіювати',1200)});
}
function addStyles(){if(document.getElementById('callGroupedStyles'))return;const st=document.createElement('style');st.id='callGroupedStyles';st.textContent=`.call-section-title{margin:20px 0 14px;padding:18px 20px;border:1px solid #bfd7fb;border-radius:15px;background:#eaf3ff;font-size:20px;font-weight:850;color:#18375f}.call-group{background:#fff;border:1px solid #d6e2f1;border-radius:15px;margin-bottom:14px;overflow:hidden;box-shadow:0 5px 18px #17385e08}.call-group-head{display:flex;align-items:center;gap:12px;padding:14px 17px;background:#f2f7ff;border-bottom:1px solid #e0e9f5;font-size:17px}.call-group-head strong{flex:1}.call-group-body{padding:17px;line-height:1.6}.call-two-col{display:grid;grid-template-columns:1fr 1fr;gap:14px}.call-script-body{min-width:0}.call-two-col .call-script-body{border:1px solid #e0e9f5;border-radius:12px;padding:14px;background:#fbfdff}.call-side-label{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#7184a2;font-weight:800;margin-bottom:8px}.call-text{white-space:pre-line}.call-copy{float:none;margin-top:12px}.call-group-head .call-copy{margin-top:0;margin-left:auto}@media(max-width:850px){.call-two-col{grid-template-columns:1fr}}`;document.head.appendChild(st)}
window.addEventListener('DOMContentLoaded',()=>{addStyles();const input=document.getElementById('callScriptSearch');if(input)input.oninput=ev=>render(ev.target.value);render()})
})();
