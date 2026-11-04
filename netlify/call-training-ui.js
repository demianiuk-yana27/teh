(()=>{
const root=document.getElementById('callTrainingApp');if(!root)return;
const guide=window.CALL_TRAINING_GUIDE;if(!guide){root.textContent='Навчальна програма тимчасово недоступна.';return}
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icons=['💬','📦','☎️'];
const subtitles=['Як перевіряти відгуки, спілкуватися з покупцями та фіксувати результат','Як повідомляти про строки відправлення та працювати із затримками','Як опрацьовувати запити, об’єднувати замовлення та оформляти Rozetka'];
let active=0;
function render(){root.innerHTML='<div class="ct-intro"><div class="ct-intro-icon">📞</div><div><h3>Програма стажування</h3><p>Три напрямки продзвону. Обери тему та проходь інструкцію послідовно.</p></div></div><div class="ct-tabs" role="tablist" aria-label="Теми стажування">'+guide.sections.map((s,i)=>'<button type="button" role="tab" aria-selected="'+(active===i)+'" data-ct-tab="'+i+'" class="'+(active===i?'selected':'')+'"><span>'+icons[i]+'</span><strong>'+esc(s.title)+'</strong><small>'+esc(subtitles[i])+'</small></button>').join('')+'</div><div class="ct-panel" role="tabpanel"><div class="ct-panel-heading"><span>'+icons[active]+'</span><div><h3>'+esc(guide.sections[active].title)+'</h3><p>'+esc(subtitles[active])+'</p></div></div><div class="ct-steps">'+guide.sections[active].blocks.map((b,i)=>'<article class="ct-step"><div class="ct-number">'+String(i+1).padStart(2,'0')+'</div><div class="ct-step-body">'+(b[0]==='list'?'<ul>'+b[1].split('\n').filter(Boolean).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'<p>'+esc(b[1])+'</p>')+'</div></article>').join('')+'</div><div class="ct-next">'+(active>0?'<button data-ct-tab="'+(active-1)+'">← Попередня тема</button>':'<span></span>')+(active<2?'<button class="ct-next-primary" data-ct-tab="'+(active+1)+'">Наступна тема →</button>':'<strong>🎉 Усі теми пройдено!</strong>')+'</div></div>';}
root.addEventListener('click',e=>{const b=e.target.closest('[data-ct-tab]');if(!b)return;active=Number(b.dataset.ctTab);render();root.scrollIntoView({behavior:'smooth',block:'start'});});
render();
})();
