(()=>{
function esc(s){return String(s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#39;'}[m]))}
const sectionRe=/(?:01|02|03|04)\s*[•]/;
const productRe=/^(?:📦|🛠|👔|💇|🔦|🔋|🎧|✂️|🔌|🧰|⌚|💡)\s/;
const metaRe=/^(?:ТОВАР|ПРОПОЗИЦІЯ|КОЛИ ПОЦІКАВИЛИСЬ АБО ЗАПИТАЛИ ЦІНУ)$/i;
const hiddenHeadRe=/^🧭 ПІДКАЗКИ МЕНЕДЖЕРУ/i;
const choiceRe=/^🔀\s*ОБЕРІТЬ/i;
const simpleHeadRe=/^(?:Привітання|📦 Наявність і відправка|🛡️ Подовжена гарантія|🚚 Звірка доставки та оплати|↳ |Товари для жінок|Товари для чоловіків|🧾 |❌ |✅ |⚠️ |🔁 |💬 |🎁 )/;
function t(s){return String(s||'').trim()}
function isSection(s){return sectionRe.test(s||'')}
function isSimpleHead(s){s=t(s);return !!s&&(simpleHeadRe.test(s)||(/^[А-ЯІЇЄҐ0-9][А-ЯІЇЄҐ0-9\s—–:|•()«»'’.,-]{4,}$/.test(s)&&s.length<120&&!metaRe.test(s)&&!productRe.test(s)&&!hiddenHeadRe.test(s)&&!choiceRe.test(s)))}
function isProduct(s){s=t(s);return productRe.test(s)||/^(?:ВАРІАНТ\s*\d+\s*[•:]?)/i.test(s)||/^[^\n]{2,45}\s+\d{7,10}(?:\s*;\s*\d{7,10}[^\n]*)?$/i.test(s)}
function isProductDetail(s){s=t(s);return /^(?:🎯 ПРОПОЗИЦІЯ|💰 (?:ЗІ ЗНИЖКОЮ|ЦІНА)|⭐ ОСОБИСТА РЕКОМЕНДАЦІЯ)/.test(s)||/^(?:додаємо|добавляємо)/i.test(s)}
function firstChoice(s){
 const lines=t(s).split(/\n+/).map(x=>x.trim()).filter(Boolean).filter(x=>!choiceRe.test(x)&&!/^(?:⬇\s*)?АБО(?:\s*⬇)?$/i.test(x));
 return lines[0]||'';
}
function makeGroup(out,section,title,type='normal'){const g={title:t(title),left:[],right:[],rows:[],type};out.push({type:'group',section,group:g});return g}
function buildGroups(rows){
 const out=[];let section=null;let group=null;let productGroup=null;
 for(let i=0;i<rows.length;i++){
  const r=rows[i],l=t(r.left),rr=t(r.right),next=rows[i+1]||{},nl=t(next.left),nr=t(next.right);
  if(isSection(l)&&!rr){section=l;group=null;productGroup=null;out.push({type:'section',title:l});continue}
  if(metaRe.test(l)&&(!rr||metaRe.test(rr)))continue;
  if(hiddenHeadRe.test(l)&&!rr){group=null;productGroup=null;continue}
  if(choiceRe.test(l)||choiceRe.test(rr)){
   const lt=firstChoice(l),rt=firstChoice(rr),title=lt&&rt?`${lt} / ${rt}`:(lt||rt);
   if(title){productGroup=makeGroup(out,section,title,'product');group=productGroup;group.rows.push(r.row)}
   continue;
  }
  const shortBeforeProposal=(s,n)=>s&&s.length<70&&!s.includes('\n')&&/^(?:🎯 ПРОПОЗИЦІЯ)/.test(n);
  if(isProduct(l)||isProduct(rr)||shortBeforeProposal(l,nl)||shortBeforeProposal(rr,nr)){
   const title=rr&&l?`${l} / ${rr}`:(l||rr);productGroup=makeGroup(out,section,title,'product');group=productGroup;group.rows.push(r.row);continue;
  }
  if(productGroup&&(isProductDetail(l)||isProductDetail(rr)||(!isSimpleHead(l)&&!isSimpleHead(rr)))){
   productGroup.rows.push(r.row);if(l)productGroup.left.push(l);if(rr)productGroup.right.push(rr);continue;
  }
  if(l&&isSimpleHead(l)&&(!rr||isSimpleHead(rr))){
   productGroup=null;const title=rr&&l!==rr?`${l} / ${rr}`:l;group=makeGroup(out,section,title);group.rows.push(r.row);continue;
  }
  if(!group)group=makeGroup(out,section,'Скрипт');
  group.rows.push(r.row);if(l)group.left.push(l);if(rr)group.right.push(rr);
 }
 return out.filter(x=>x.type!=='group'||x.group.left.length||x.group.right.length);
}
function copyBtn(text){return `<button class="copy call-copy" data-copy="${encodeURIComponent(text)}">▣ Скопіювати</button>`}
function cleanBody(text){return t(text).replace(/^\s*(?:🔀\s*ОБЕРІТЬ[^\n]*|⬇\s*АБО\s*⬇)\s*$/gmi,'').replace(/\n{3,}/g,'\n\n').trim()}
function formatBody(text){return esc(cleanBody(text)).replace(/^(🎯 ПРОПОЗИЦІЯ|💰 (?:ЗІ ЗНИЖКОЮ|ЦІНА)[^\n]*|⭐ ОСОБИСТА РЕКОМЕНДАЦІЯ)/gm,'<strong class="call-detail-label">$1</strong>')}
function renderGroup(x){const g=x.group,left=cleanBody(g.left.join('\n\n')),right=cleanBody(g.right.join('\n\n')),both=left&&right;if(!left&&!right)return '';return `<article class="call-group${g.type==='product'?' call-product':''}"><div class="call-group-head"><strong>${esc(g.title)}</strong>${!both&&left?copyBtn(left):''}</div><div class="call-group-body${both?' call-two-col':''}">${left?`<div class="call-script-body">${both?'<div class="call-side-label">Для жінок</div>':''}<div class="call-text">${formatBody(left)}</div>${both?copyBtn(left):''}</div>`:''}${right?`<div class="call-script-body">${both?'<div class="call-side-label">Для чоловіків</div>':''}<div class="call-text">${formatBody(right)}</div>${copyBtn(right)}</div>`:''}</div></article>`}
function render(q=''){
 const root=document.getElementById('callScriptList');if(!root)return;q=q.toLowerCase().trim();let items=buildGroups(window.CALL_SCRIPT_ROWS||[]);
 if(q)items=items.filter(x=>x.type==='section'||((x.group.title+' '+x.group.left.join(' ')+' '+x.group.right.join(' ')).toLowerCase().includes(q)));
 if(q)items=items.filter((x,i)=>x.type!=='section'||items.slice(i+1).some(y=>y.type==='group'&&y.section===x.title));
 const groups=items.filter(x=>x.type==='group'),total=document.getElementById('callScriptTotal');if(total)total.textContent=groups.length;
 root.innerHTML=items.map(x=>x.type==='section'?`<div class="call-section-title">${esc(x.title)}</div>`:renderGroup(x)).join('')||'<div class="empty">Нічого не знайдено.</div>';
 root.querySelectorAll('[data-copy]').forEach(btn=>btn.onclick=()=>{navigator.clipboard.writeText(decodeURIComponent(btn.dataset.copy));btn.textContent='✓ Скопійовано';setTimeout(()=>btn.textContent='▣ Скопіювати',1200)});
}
function addStyles(){if(document.getElementById('callGroupedStyles'))return;const st=document.createElement('style');st.id='callGroupedStyles';st.textContent=`.call-section-title{margin:20px 0 14px;padding:18px 20px;border:1px solid #bfd7fb;border-radius:15px;background:#eaf3ff;font-size:20px;font-weight:850;color:#18375f}.call-group{background:#fff;border:1px solid #d6e2f1;border-radius:15px;margin-bottom:18px;overflow:hidden;box-shadow:0 5px 18px #17385e08}.call-group-head{display:flex;align-items:center;gap:12px;padding:15px 18px;background:#f2f7ff;border-bottom:1px solid #e0e9f5;font-size:17px;line-height:1.4}.call-group-head strong{flex:1}.call-product .call-group-head{background:#eaf3ff}.call-group-body{padding:17px;line-height:1.6}.call-two-col{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:14px;align-items:stretch}.call-script-body{min-width:0}.call-two-col .call-script-body{display:flex;flex-direction:column;border:1px solid #e0e9f5;border-radius:12px;padding:15px;background:#fbfdff}.call-side-label{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:#7184a2;font-weight:800;margin-bottom:9px}.call-text{white-space:pre-line;overflow-wrap:anywhere}.call-detail-label{display:block;margin:18px 0 7px;color:#23476f}.call-text .call-detail-label:first-child{margin-top:0}.call-copy{float:none;margin-top:16px;align-self:flex-start}.call-group-head .call-copy{margin-top:0;margin-left:auto}@media(max-width:850px){.call-two-col{grid-template-columns:1fr}}`;document.head.appendChild(st)}
window.addEventListener('DOMContentLoaded',()=>{addStyles();const input=document.getElementById('callScriptSearch');if(input)input.oninput=ev=>render(ev.target.value);render()})
})();
