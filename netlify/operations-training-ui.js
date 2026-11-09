(()=>{
const root=document.getElementById('operationsTrainingApp');
if(!root)return;
const guide=window.OPERATIONS_TRAINING_GUIDE;
if(!guide){root.textContent='Програма стажування тимчасово недоступна.';return;}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let active=0,search='';
const completedKey='tech-operations-training-completed-v1';
let completed={};
try{completed=JSON.parse(localStorage.getItem(completedKey)||'{}')||{}}catch(_){}
const allCount=guide.sections.reduce((n,s)=>n+s.items.length,0);
const totalDone=()=>guide.sections.reduce((n,s,si)=>n+s.items.filter((_,i)=>completed[si+'-'+i]).length,0);
function render(){
 const section=guide.sections[active];
 const visible=section.items.map((item,i)=>({item,i})).filter(x=>!search||x.item.join(' ').toLocaleLowerCase('uk').includes(search.toLocaleLowerCase('uk')));
 root.innerHTML='<div class="ot-intro"><div class="ot-icon">👥</div><div><h3>Програма стажування</h3><p>Інструкції з робочих процесів операційного менеджера. Поки без фото та відео.</p></div></div>'+
 '<div class="ot-summary"><span>Опрацьовано <b>'+totalDone()+' із '+allCount()+'</b> тем</span><div class="ot-progress"><div style="width:'+(100*totalDone()/allCount)+'%"></div></div></div>'+
 '<div class="ot-tabs" role="tablist" aria-label="Розділи стажування">'+guide.sections.map((s,i)=>'<button type="button" role="tab" aria-selected="'+(active===i)+'" data-ot-tab="'+i+'" class="'+(active===i?'selected':'')+'"><strong>'+(i===0?'📅 ':'🗓️ ')+esc(s.title)+'</strong><small>'+s.items.length+' тем</small></button>').join('')+'</div>'+
 '<label class="ot-search-label" for="otSearch">Пошук по завданнях</label><input id="otSearch" class="ot-search" type="search" placeholder="Назва або текст інструкції..." value="'+esc(search)+'">'+
 '<div class="ot-list">'+(visible.length?visible.map(({item,i})=>'<details class="ot-item" data-ot-item="'+i+'"><summary><span class="ot-num">'+String(i+1).padStart(2,'0')+'</span><strong>'+esc(item[0])+'</strong><span class="ot-arrow">⌄</span></summary><div class="ot-detail">'+esc(item[1]).replace(/\n/g,'<br>')+'<label class="ot-done"><input type="checkbox" data-ot-done="'+active+'-'+i+'" '+(completed[active+'-'+i]?'checked':'')+'> Тему опрацьовано</label></div></details>').join(''):'<p class="ot-empty">За цим запитом нічого не знайдено.</p>')+'</div>'+
 '<div class="ot-bottom">'+(active>0?'<button type="button" data-ot-tab="'+(active-1)+'">← Попередній розділ</button>':'<span></span>')+(active<guide.sections.length-1?'<button type="button" class="ot-primary" data-ot-tab="'+(active+1)+'">Наступний розділ →</button>':'<span>🎓 Кінець програми</span>')+'</div>';
}
root.addEventListener('click',e=>{const b=e.target.closest('[data-ot-tab]');if(!b)return;active=Number(b.dataset.otTab);search='';render();root.scrollIntoView({behavior:'smooth',block:'start'});});
root.addEventListener('input',e=>{if(e.target.id!=='otSearch')return;const pos=e.target.selectionStart;search=e.target.value;render();const inp=root.querySelector('#otSearch');inp.focus();inp.setSelectionRange(pos,pos);});
root.addEventListener('change',e=>{if(!e.target.matches('[data-ot-done]'))return;completed[e.target.dataset.otDone]=e.target.checked;try{localStorage.setItem(completedKey,JSON.stringify(completed))}catch(_){}const n=root.querySelector('.ot-summary b');if(n)n.textContent=totalDone()+' із '+allCount();const bar=root.querySelector('.ot-progress>div');if(bar)bar.style.width=(100*totalDone()/allCount())+'%';});
render();
})();