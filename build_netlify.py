# Cloudflare rebuild trigger: verified five-reply test queue (2026-11-09).
# Restore full positive reviews UI after overlapping deployment (2026-11-09).
# Cloudflare refresh: guarded 3-reply queue (2026-11-09).
# Cloudflare deployment refresh: manual absent-reply journal status (2026-11-09).
# Deployment refresh: positive reply queue UI (2026-11-09).
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


# Positive reviews: isolated read-only preview under Operational Managers.
s = s.replace('data-view="dorobky">• Доробки</div>',
              'data-view="dorobky">• Доробки</div><div class="sub" data-view="positive-reviews">• Позитивні відгуки</div>', 1)
s = s.replace('data-target-view="dorobky"><span',
              'data-target-view="dorobky"><span', 1)
positive_html = """<section class="view" id="positive-reviews"><div class="pagehead"><div class="pageicon">⭐</div><div><h2>Позитивні відгуки</h2><p>Попередній перегляд і виключення перед автоматичними відповідями</p></div></div>
<div class="card"><h3>Збір відгуків</h3><p>Перегляньте текст покупця та позначте прапорцем відгуки, які потребують індивідуальної відповіді. Збираємо з усіх активних магазинів (TRUE) у Google Sheets. Автоматичне надсилання вимкнено.</p>
<label for="positiveDay">Дата відгуків</label> <input type="date" id="positiveDay"/>
<button class="run" type="button" onclick="loadPositivePreview(this)">🔎 Зібрати з усіх магазинів</button>
<button class="run" type="button" onclick="retryPositiveFailed(this)" style="background:#64748b">🔄 Повторити невдалі</button>
<button class="run" type="button" onclick="probePositiveShopSwitch(this)" style="background:#475569">🧪 Перевірити 2 магазини</button>
<div style="margin-top:18px;padding:16px;border:1px solid #dbe3ee;border-radius:12px">
<h3>🧪 Перевірка майбутніх відповідей — без публікації</h3>
<p style="font-size:13px;color:#64748b">Вставте ваші готові шаблони: один шаблон на рядок. Вони зберігаються лише в цьому браузері. Натисніть «Підготувати план», щоб побачити, який текст дістанеться кожному відгуку. Жодних повідомлень у Prom не надсилаємо.</p>
<textarea id="positiveTemplates" rows="5" style="width:100%;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;padding:10px" placeholder="Один шаблон відповіді на рядок"></textarea>
<button class="run" type="button" onclick="positiveBuildDrafts(this)" style="background:#7c3aed;margin-top:8px">📝 Підготувати план відповідей</button>
<div style="margin:14px 0;padding:12px;border:1px solid #e2e8f0;border-radius:10px">
<strong>Контрольована тестова черга — максимум 5 за запуск</strong>
<p style="font-size:12px;color:#64748b">Після кожної відповіді сервер звіряє точний текст у Prom. Пауза 4 секунди. За будь-якої помилки черга зупиняється без повтору. Журнал поки лише в цьому браузері — не запускайте одночасно з інших пристроїв.</p>
<label for="positiveBatchLimit">Кількість</label> <input id="positiveBatchLimit" type="number" min="1" max="5" value="3" style="width:65px"/>
<button class="run" type="button" onclick="positiveStartQueue()" style="background:#b45309">🚀 Запустити підтверджену чергу</button>
<button class="run" type="button" onclick="positiveStopQueue()" style="background:#64748b">⏹ Зупинити після поточного</button>
<div class="status" id="positiveQueueStatus"></div><div style="margin-top:10px"><button class="run" type="button" onclick="positiveShowJournal(this)" style="background:#475569">📋 Показати журнал спроб</button><button class="run" type="button" onclick="positiveExportJournal()" style="background:#475569">⬇️ Експорт журналу JSON</button><div id="positiveJournalView" style="margin-top:8px"></div></div>
</div><div class="status" id="positiveDraftStatus"></div><div id="positiveDraftList"></div>
</div>
<div class="status" id="positiveShopProbeStatus" style="white-space:pre-wrap"></div>
<div class="status" id="positiveStatus" style="white-space:pre-wrap"></div><div id="positiveList"></div></div></section>"""
s = s.replace('</main>', positive_html + '</main>', 1)
s = s.replace('data-target-view="ordercount"><span', 'data-target-view="ordercount"><span', 1)
positive_script = """<script>
async function probePositiveShopSwitch(button){
 const out=document.getElementById('positiveShopProbeStatus');
 button.disabled=true;out.textContent='⏳ Перевіряємо два магазини без публікації…';
 try{
  const res=await fetch('/api/positive/shop-switch-probe',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  const data=await res.json();if(!res.ok||data.status!=='ok')throw Error(data.message||'Помилка перевірки');
  const lines=(data.shops||[]).map(x=>'Акаунт '+x.account_id+': sign-to HTTP '+String(x.switch_status)+', перехід у CMS '+(x.redirect_to_cms?'так':'ні')+', відгуки HTTP '+String(x.reviews_status)+', company_id '+(x.company_ids||[]).join(', ')+', відгуків на сторінці '+String(x.review_count)+(x.error?', помилка: '+x.error:''));
  out.textContent=lines.join('\\n')+'\\nРізні магазини підтверджені: '+(data.distinct_companies?'✅ так':'⚠️ ні')+'. Тест лише читання.';
 }catch(e){out.textContent='❌ '+e.message}
 finally{button.disabled=false}
}
const positiveCachePrefix='teh-positive-v2:';
let positiveRunBusy=false;
function positiveCacheKey(day){return positiveCachePrefix+day}
function positiveRead(day){
 try{const v=JSON.parse(localStorage.getItem(positiveCacheKey(day))||'null');return v&&v.shops&&typeof v.shops==='object'?v:{shops:{},flags:[]}}catch(e){return {shops:{},flags:[]}}
}
function positiveSave(day,v){
 try{localStorage.setItem(positiveCacheKey(day),JSON.stringify(v))}
 catch(e){document.getElementById('positiveStatus').textContent+=' ⚠️ Не вдалося зберегти результат у браузері.'}
}
function positiveRender(day){
 const out=document.getElementById('positiveStatus'),list=document.getElementById('positiveList');
 const state=positiveRead(day), shops=Object.values(state.shops);
 const errors=shops.filter(x=>!x.complete||x.error), successful=shops.filter(x=>x.complete&&!x.error);
 const data={shops,reviews:successful.flatMap(x=>x.reviews||[]),pages_checked:shops.reduce((n,x)=>n+(x.pages_checked||0),0)};
 const seen=new Set();data.reviews=data.reviews.filter(x=>{const key=x.company_id+':'+x.id;if(seen.has(key))return false;seen.add(key);return true});
 const counts={unanswered:0,answered:0,needs_check:0};
 for(const x of data.reviews)counts[x.reply_status]=(counts[x.reply_status]||0)+1;
 out.textContent='За '+day+': успішно '+successful.length+'; не вдалося '+errors.length+'; позитивних відгуків '+data.reviews.length+'; без відповіді '+counts.unanswered+'; вже з коментарем '+counts.answered+'; сторінок '+data.pages_checked+'. '+(errors.length?'⚠️ Повторіть: '+errors.map(x=>x.shop_name).join(', ')+'.':'')+' Публікація вимкнена.';
 list.replaceChildren();
  const toolbar=document.createElement('div');toolbar.style.cssText='padding:14px 4px;font-weight:700;color:#334155';list.append(toolbar);
  const eligible=data.reviews.filter(r=>r.reply_status==='unanswered');
  const exclusions=new Set(state.flags||[]);
  const suspicious=/але|проте|однак|хоча|жах|поган|обман|шахра|хам|груб|брак|поламан|зламан|не рекоменд|не працю|не відповіда|повернен|розчар|скарг|проблем|дефект|хірн|фігн|твар|лайно|говн|ужас|плох|затрим|довго чека/iu;
  function update(){toolbar.textContent='До відповіді: '+(eligible.length-exclusions.size)+' · Виключено: '+exclusions.size+' · Публікація вимкнена';}
  for(const review of data.reviews){
   const row=document.createElement('article');row.style.cssText='display:flex;gap:16px;justify-content:space-between;align-items:flex-start;border:1px solid #e2e8f0;border-radius:14px;padding:18px;margin:10px 0;background:#fff';
   const main=document.createElement('div');main.style.cssText='min-width:0;flex:1';
   const title=document.createElement('div');title.style.cssText='font-size:13px;color:#64748b';
   const stars=document.createElement('span');stars.style.cssText='color:#8b5cf6;font-size:17px;letter-spacing:2px;margin-right:12px';stars.textContent='★'.repeat(review.rating);
   title.append(stars,document.createTextNode((review.shop_name||'Магазин')+' · № '+review.id+' · '+(review.date_raw||'Дата невідома').slice(0,10)));main.append(title);
   const body=document.createElement('p');body.style.cssText='font-size:15px;line-height:1.55;white-space:pre-wrap;overflow-wrap:anywhere;margin:12px 0 0';body.textContent=review.text||'Без тексту';main.append(body);
   if(review.reply_status==='unanswered'&&review.text&&suspicious.test(review.text)){
    row.style.borderColor='#fbbf24';row.style.background='#fffbeb';
    const warning=document.createElement('div');warning.style.cssText='color:#92400e;font-size:12px;font-weight:700;margin-top:10px';
    warning.textContent='⚠️ Перевірте зміст — можливе невдоволення';main.append(warning);
   }
   if(review.reply_status!=='unanswered'){
    row.style.background='#f8fafc';row.style.opacity='.7';
    const status=document.createElement('div');status.style.cssText='font-size:12px;color:#64748b;margin-top:9px';
    status.textContent=review.reply_status==='answered'?'Вже є коментар — пропущено':'Статус невизначений — пропущено';main.append(status);
   }
   row.append(main);
   if(review.reply_status==='unanswered'){
    const label=document.createElement('label');label.title='Виключити з автоматичних відповідей';
    label.style.cssText='position:relative;display:flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;width:46px;height:46px;border-radius:12px;background:#f1f5f9;border:1px solid #e2e8f0';
    const check=document.createElement('input');check.type='checkbox';check.setAttribute('aria-label','Виключити відгук № '+review.id);
    check.style.cssText='position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:pointer';
    const emoji=document.createElement('span');emoji.textContent='🚩';emoji.style.cssText='font-size:23px;filter:grayscale(1);opacity:.55;pointer-events:none';
    if(exclusions.has(review.company_id+':'+review.id)){check.checked=true;row.style.background='#fff1f2';row.style.borderColor='#fda4af';label.style.background='#ffe4e6';emoji.style.filter='none';emoji.style.opacity='1'}
    check.addEventListener('change',()=>{if(check.checked){exclusions.add(review.company_id+':'+review.id);row.style.background='#fff1f2';row.style.borderColor='#fda4af';label.style.background='#ffe4e6';emoji.style.filter='none';emoji.style.opacity='1';}else{exclusions.delete(review.company_id+':'+review.id);row.style.background=suspicious.test(review.text||'')?'#fffbeb':'#fff';row.style.borderColor=suspicious.test(review.text||'')?'#fbbf24':'#e2e8f0';label.style.background='#f1f5f9';emoji.style.filter='grayscale(1)';emoji.style.opacity='.55';}state.flags=[...exclusions];positiveSave(day,state);update()});
    label.append(check,emoji);row.append(label);
   }
   list.append(row);
  }
  update();
  const note=document.createElement('p');note.style.cssText='font-size:12px;color:#64748b;margin-top:14px';note.textContent='🚩 — виключити відгук. Позначки зберігаються у цьому браузері для вибраної дати. Відправлення відповідей вимкнено.';list.append(note);
}
async function positiveFetchShop(day,offset,companyId,skipIds){
 const body=companyId?{date:day,offset:0,company_id:companyId}:{date:day,offset,skip_company_ids:skipIds||[]};
 const res=await fetch('/api/positive/shops-batch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 if(!(res.headers.get('content-type')||'').includes('application/json'))throw Error('Сервер повернув HTML (HTTP '+res.status+')');
 const batch=await res.json();if(!res.ok||batch.status!=='ok')throw Error(batch.message||'Помилка збору');
 return batch;
}
async function loadPositivePreview(button,retryOnly=false){
 const day=document.getElementById('positiveDay').value,out=document.getElementById('positiveStatus');
 if(!day){out.textContent='❌ Оберіть дату.';return}
 if(positiveRunBusy)return;
 positiveRunBusy=true;
 const controls=document.querySelectorAll('#positive-reviews button.run');controls.forEach(b=>b.disabled=true);
 let state=positiveRead(day);
 try{
  if(retryOnly){
   const failed=Object.values(state.shops).filter(x=>!x.complete||x.error);
   if(!failed.length){positiveRender(day);return}
   for(let i=0;i<failed.length;i++){
    const shop=failed[i];
    out.textContent='⏳ Повтор '+(i+1)+'/'+failed.length+': '+shop.shop_name;
    try{
     const batch=await positiveFetchShop(day,0,shop.company_id);
     const result=batch.shops[0];
     if(result&&String(result.company_id)===String(shop.company_id)){state.shops[shop.company_id]=result;positiveSave(day,state)}
    }catch(e){state.shops[shop.company_id]={...shop,complete:false,error:e.message};positiveSave(day,state)}
    positiveRender(day);
   }
  }else{
   let offset=0,total=1;
   while(offset<total){
    out.textContent='⏳ Магазин '+(offset+1)+'/'+(total===1?'…':total)+'; успішні результати збережено';
    const skipIds=Object.values(state.shops).filter(x=>x.complete&&!x.error).map(x=>x.company_id);
    const batch=await positiveFetchShop(day,offset,null,skipIds);
    total=batch.total_shops;
    if(!batch.shops.length)throw Error('Порожня відповідь магазину');
    for(const shop of batch.shops){
     if(shop.skipped_cached)continue;
     const previous=state.shops[shop.company_id];
     if(!previous||!previous.complete||previous.error||shop.complete&&!shop.error){
      state.shops[shop.company_id]=shop;
     }
    }
    positiveSave(day,state);
    offset=batch.next_offset;
   }
  }
 }catch(e){out.textContent='❌ '+e.message+'; попередні результати збережені.'}
 finally{positiveRunBusy=false;controls.forEach(b=>b.disabled=false);positiveRender(day)}
}
function retryPositiveFailed(button){loadPositivePreview(button,true)}
let positiveQueueStop=false;
let positiveQueueRunning=false;
let positiveDraftPlan=[];
function positiveJournalKey(){return 'teh-positive-journal-v1'}
function positiveMayPublish(key,journal){
 const entry=journal[key];
 return !entry||entry.status==='manually_absent';
}
function positiveJournalRead(){
 try{const v=JSON.parse(localStorage.getItem(positiveJournalKey())||'{}');return v&&typeof v==='object'?v:{}}catch(e){return {}}
}
function positiveShowJournal(){
 const target=document.getElementById('positiveJournalView');target.replaceChildren();
 const journal=positiveJournalRead(),entries=Object.entries(journal).sort((a,b)=>String(a[1].at||'').localeCompare(String(b[1].at||'')));
 if(!entries.length){target.textContent='Журнал поки порожній.';return}
 const intro=document.createElement('p');intro.style.cssText='font-size:13px;color:#475569;margin:8px 0';
 intro.textContent='Перевіряйте кожен відгук у зазначеному магазині. Номер нижче — ID відгуку, а не замовлення. Ручне підтвердження не надсилає нічого в Prom.';
 target.append(intro);
 for(const [key,item] of entries){
  const parts=key.split(':'),company=parts[0],opinion=parts[1]||key;
  const card=document.createElement('div');card.style.cssText='border:1px solid #cbd5e1;border-radius:10px;padding:12px;margin:8px 0;background:#fff';
  const name=document.createElement('div');name.style.cssText='font-weight:800;font-size:16px;color:#172554';
  name.textContent='🏪 '+(item.shop||'Магазин '+company);
  const id=document.createElement('div');id.style.cssText='font-size:14px;font-weight:700;margin-top:4px';
  id.textContent='ID відгуку №'+opinion+' · company_id '+company;
  const stamp=document.createElement('div');stamp.style.cssText='font-size:12px;color:#64748b;margin-top:4px';
  stamp.textContent='Спроба: '+(item.at?new Date(item.at).toLocaleString('uk-UA'):'невідомо');
  const state=document.createElement('div');state.style.cssText='font-size:13px;margin-top:6px;font-weight:700';
  const statusLabel=()=>item.status==='manually_verified'?'✅ Підтверджено вручну в Prom':item.status==='sent'?'🟡 API підтвердив; у Prom не перевірено':item.status==='attempted'?'⚠️ Невизначено — перевірити в Prom':item.status==='manually_absent'?'❌ Перевірено — відповіді немає':item.status==='verified'?'✅ Перевірено сервером у Prom':'⚠️ '+(item.status||'Невідомо');
  state.textContent=statusLabel();
  const reply=document.createElement('div');reply.style.cssText='font-size:12px;margin-top:6px;white-space:pre-wrap;color:#475569';
  reply.textContent='Текст спроби: '+(item.comment||'не збережено');
  card.append(name,id,stamp,state,reply);
  if(item.status!=='manually_verified'){
   const verify=document.createElement('button');verify.type='button';verify.className='run';
   verify.style.cssText='background:#64748b;margin-top:8px';
   verify.textContent='✅ Я перевірила коментар у Prom';
   verify.addEventListener('click',()=>{
    if(!confirm('Підтверджуєте, що саме цей текст опублікований у магазині '+(item.shop||company)+' під відгуком №'+opinion+'?'))return;
    const latest=positiveJournalRead();
    if(!latest[key])return;
    latest[key]={...latest[key],status:'manually_verified',verified_at:new Date().toISOString()};
    if(!positiveJournalWrite(latest)){alert('Не вдалося зберегти підтвердження.');return}
    positiveShowJournal();
   });
   card.append(verify);
  }
  if(item.status!=='manually_absent'&&item.status!=='manually_verified'){
   const absent=document.createElement('button');absent.type='button';absent.className='run';
   absent.style.cssText='background:#9f1239;margin-top:8px;margin-left:6px';
   absent.textContent='❌ Перевірила — відповіді немає';
   absent.addEventListener('click',()=>{
    if(!confirm('Ви перевірили саме магазин '+(item.shop||company)+' та відгук №'+opinion+' і відповіді там немає? Це лише запис у журналі, нічого не надсилається.'))return;
    const latest=positiveJournalRead();
    if(!latest[key])return;
    latest[key]={...latest[key],status:'manually_absent',checked_at:new Date().toISOString()};
    if(!positiveJournalWrite(latest)){alert('Не вдалося зберегти результат перевірки.');return}
    positiveShowJournal();
   });
   card.append(absent);
  }
  target.append(card);
 }
}
function positiveExportJournal(){
 const blob=new Blob([JSON.stringify(positiveJournalRead(),null,2)],{type:'application/json'});
 const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='positive-reply-journal.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function positiveJournalWrite(journal){
 try{localStorage.setItem(positiveJournalKey(),JSON.stringify(journal));return true}catch(e){return false}
}
function positiveStopQueue(){positiveQueueStop=true;const el=document.getElementById('positiveQueueStatus');if(el)el.textContent='⏹ Зупинка запитана. Поточний запит буде завершено.'}
async function positiveParsePublishResponse(res,startedAt){
 const type=(res.headers.get('content-type')||'').toLowerCase();
 const duration=Math.round(performance.now()-startedAt);
 const ray=res.headers.get('cf-ray')||'—';
 const requestId=res.headers.get('x-request-id')||'—';
 const diagnostic='HTTP '+res.status+' '+(res.statusText||'')+', тип '+(type||'не вказано')+', '+duration+' мс, CF-Ray '+ray+', Request-ID '+requestId;
 if(!type.includes('application/json')){
  // Never display response HTML: proxy error pages can contain sensitive details.
  throw Error('Неочікувана відповідь сервера ('+diagnostic+'). Результат публікації невідомий');
 }
 let result;
 try{result=await res.json()}catch(_){throw Error('Пошкоджений JSON ('+diagnostic+'). Результат публікації невідомий')}
 if(!res.ok||result.status!=='ok'||result.verified!==true){
  throw Error((result.message||'Prom не підтвердив точний текст відповіді')+' ('+diagnostic+')');
 }
 return result;
}
async function positiveStartQueue(){
 const out=document.getElementById('positiveQueueStatus'),day=document.getElementById('positiveDay').value;
 if(positiveQueueRunning||positiveRunBusy){out.textContent='Інший процес уже виконується.';return}
 const limit=Number(document.getElementById('positiveBatchLimit').value);
 if(!Number.isInteger(limit)||limit<1||limit>5){out.textContent='Оберіть від 1 до 5 відповідей.';return}
 const state=positiveRead(day),flags=new Set(state.flags||[]),journal=positiveJournalRead();
 const shops=Object.values(state.shops);
 if(!shops.length||shops.some(x=>!x.complete||x.error)){out.textContent='Спершу завершіть збір усіх магазинів.';return}
 const candidates=positiveDraftPlan.filter(x=>{
  const key=x.company_id+':'+x.id,shop=state.shops[x.company_id];
  const fresh=shop&&(shop.reviews||[]).find(r=>String(r.id)===String(x.id));
  return fresh&&fresh.reply_status==='unanswered'&&!flags.has(key)&&positiveMayPublish(key,journal);
 }).slice(0,limit);
 if(!candidates.length){out.textContent='Немає доступних чернеток для запуску. Перевірте журнал та сформуйте план.';return}
 const names=candidates.map(x=>x.shop_name+' №'+x.id).join('\\n');
 const confirmation=prompt('СПРАВЖНЯ ПУБЛІКАЦІЯ В PROM.\\nБуде надіслано до '+candidates.length+' відповідей:\\n'+names+'\\n\\nДля запуску введіть НАДІСЛАТИ '+candidates.length);
 if(confirmation!=='НАДІСЛАТИ '+candidates.length)return;
 positiveQueueStop=false;positiveQueueRunning=true;positiveRunBusy=true;
 let sent=0;
 try{
  for(const item of candidates){
   if(positiveQueueStop)break;
   const key=item.company_id+':'+item.id,now=positiveRead(day);
   const shop=now.shops[item.company_id],review=shop&&(shop.reviews||[]).find(r=>String(r.id)===String(item.id));
   if(!shop||!shop.complete||shop.error||!review||review.reply_status!=='unanswered'||(now.flags||[]).includes(key)){out.textContent='⏹ Статус змінився для '+key+'. Чергу зупинено.';break}
   if(!positiveMayPublish(key,positiveJournalRead())){out.textContent='⏹ Невизначена або успішна спроба для '+key+'. Чергу зупинено.';break}
   const currentJournal=positiveJournalRead();
   const isRetry=currentJournal[key]?.status==='manually_absent';
   currentJournal[key]={status:'attempted',day,shop:item.shop_name,comment:item.comment,at:new Date().toISOString(),previous_attempt:currentJournal[key]||null};
   if(!positiveJournalWrite(currentJournal)){out.textContent='⏹ Неможливо записати журнал. Відправлення скасовано.';break}
   out.textContent='⏳ Надсилаємо '+key+' ('+(sent+1)+'/'+candidates.length+')';
   try{
    const startedAt=performance.now();
    const res=await fetch('/api/positive/publish-one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({company_id:item.company_id,opinion_id:item.id,comment:item.comment,retry_verified_absent:isRetry,retry_confirmation:isRetry?'ПЕРЕВІРЕНО НЕМАЄ':null,confirmation:'НАДІСЛАТИ'})});
    const result=await positiveParsePublishResponse(res,startedAt);
    const done=positiveJournalRead();done[key]={...done[key],status:'verified',verified_at:new Date().toISOString()};positiveJournalWrite(done);
    review.reply_status='answered';positiveSave(day,now);sent++;
    out.textContent='✅ Підтверджено в Prom '+sent+' із '+candidates.length+'.';
   }catch(e){out.textContent='⛔ Зупинено після '+sent+' успішних. '+key+': '+e.message+'. Запис позначено як невизначений; перевірте Prom вручну.';break}
   if(!positiveQueueStop&&sent<candidates.length)await new Promise(resolve=>setTimeout(resolve,4000));
  }
 }finally{positiveQueueRunning=false;positiveRunBusy=false;positiveRender(day);out.textContent+=' Журнал спроб збережено в браузері.'}
}
function positiveBuildDrafts(button){
 const day=document.getElementById('positiveDay').value, status=document.getElementById('positiveDraftStatus');
 const target=document.getElementById('positiveDraftList');target.replaceChildren();
 if(!day){status.textContent='❌ Спочатку виберіть дату.';return}
 const templates=document.getElementById('positiveTemplates').value.split(/\\r?\\n/).map(x=>x.trim()).filter(Boolean);
 if(!templates.length){status.textContent='❌ Додайте хоча б один шаблон відповіді.';return}
 try{localStorage.setItem('teh-positive-templates-v1',JSON.stringify(templates))}catch(e){}
 const state=positiveRead(day), shops=Object.values(state.shops);
 const failed=shops.filter(x=>!x.complete||x.error);
 if(!shops.length){status.textContent='❌ Спочатку зберіть відгуки.';return}
 if(failed.length){status.textContent='⚠️ Спершу повторіть невдалі магазини: '+failed.map(x=>x.shop_name).join(', ');return}
 const flags=new Set(state.flags||[]),journal=positiveJournalRead();
 const seen=new Set(),eligible=[];
 for(const shop of shops){
  for(const review of shop.reviews||[]){
   const key=String(review.company_id)+':'+String(review.id);
   if(seen.has(key))continue;seen.add(key);
   if(review.reply_status!=='unanswered'||flags.has(key)||!positiveMayPublish(key,journal))continue;
   eligible.push(review);
  }
 }
 eligible.sort((a,b)=>String(a.company_id).localeCompare(String(b.company_id))||String(a.id).localeCompare(String(b.id),undefined,{numeric:true}));
 status.textContent='🧪 Підготовлено '+eligible.length+' чернеток за '+day+' із '+templates.length+' шаблонів. Успішні та невизначені спроби виключені; перевірені без відповіді доступні для повторної спроби. Перед публікацією сервер перевіряє актуальний стан у Prom.';
 positiveDraftPlan=eligible.map((review,i)=>({...review,comment:templates[i%templates.length]}));
 const fragment=document.createDocumentFragment();
 for(let i=0;i<eligible.length;i++){
  const review=eligible[i],wrap=document.createElement('div');
  wrap.style.cssText='padding:12px;margin:8px 0;border:1px solid #e2e8f0;border-radius:10px;background:#fafaff';
  const heading=document.createElement('div');heading.style.cssText='font-size:12px;color:#64748b;font-weight:700';
  heading.textContent=review.shop_name+' · № '+review.id+' · Шаблон '+(i%templates.length+1);
  const buyer=document.createElement('p');buyer.textContent='Покупець: '+(review.text||'Без тексту');buyer.style.cssText='font-size:13px';
  const reply=document.createElement('p');reply.textContent='Чернетка: '+templates[i%templates.length];reply.style.cssText='font-size:14px;white-space:pre-wrap;font-weight:600';
  const send=document.createElement('button');send.type='button';send.className='run';
  send.style.cssText='background:#b45309;margin-top:6px';
  send.textContent='🧪 Надіслати лише цю відповідь';
  send.addEventListener('click',async()=>{
   if(positiveRunBusy)return;
   if(!positiveMayPublish(String(review.company_id)+':'+String(review.id),positiveJournalRead())){alert('Відгук уже має спробу. Повтор дозволений лише зі статусом «Перевірено — відповіді немає».');return}
   const fresh=positiveRead(day),stored=fresh.shops[String(review.company_id)];
   const current=stored&&(stored.reviews||[]).find(x=>String(x.id)===String(review.id));
   if(!stored||!stored.complete||stored.error||!current||current.reply_status!=='unanswered'||(fresh.flags||[]).includes(String(review.company_id)+':'+String(review.id))){
    alert('Відгук уже виключено або його статус змінився. Публікацію скасовано.');return;
   }
   const message=templates[i%templates.length];
   const confirmation=prompt('УВАГА: це СПРАВЖНЯ публікація в Prom.\\nМагазин: '+review.shop_name+'\\nВідгук: №'+review.id+'\\nТекст: '+message+'\\n\\nДля надсилання рівно ОДНІЄЇ відповіді введіть НАДІСЛАТИ');
   if(confirmation!=='НАДІСЛАТИ')return;
   const key=String(review.company_id)+':'+String(review.id);
   const journal=positiveJournalRead();
   if(!positiveMayPublish(key,journal)){alert('Відгук уже має спробу. Перевірте статус у журналі.');return}
   const isRetry=journal[key]?.status==='manually_absent';
   journal[key]={status:'attempted',day,shop:review.shop_name,comment:message,at:new Date().toISOString(),previous_attempt:journal[key]||null};
   if(!positiveJournalWrite(journal)){alert('Не вдалося зберегти журнал. Відправлення скасовано.');return}
   positiveRunBusy=true;send.disabled=true;
   const status=document.getElementById('positiveDraftStatus');
   status.textContent='⏳ Надсилаємо одну відповідь і перевіряємо її в Prom…';
   try{
    const startedAt=performance.now();
    const res=await fetch('/api/positive/publish-one',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
     company_id:String(review.company_id),opinion_id:String(review.id),comment:message,retry_verified_absent:isRetry,retry_confirmation:isRetry?'ПЕРЕВІРЕНО НЕМАЄ':null,confirmation
    })});
    const result=await positiveParsePublishResponse(res,startedAt);
    const updated=positiveJournalRead();
    updated[key]={...updated[key],status:'verified',verified_at:new Date().toISOString()};
    positiveJournalWrite(updated);
    current.reply_status='answered';positiveSave(day,fresh);
    send.textContent='✅ Перевірено в Prom';send.disabled=true;
    status.textContent='✅ Відповідь №'+review.id+' підтверджено повторним читанням Prom.';
    positiveRender(day);
   }catch(e){
    status.textContent='⚠️ '+e.message+' Спроба записана в журналі як невизначена. Не надсилайте повторно без ручної перевірки в Prom.';
    send.disabled=true;send.textContent='⚠️ Перевірте журнал';
   }
   finally{positiveRunBusy=false}
  });
  wrap.append(heading,buyer,reply,send);fragment.append(wrap);
 }
 target.append(fragment);
}
function positiveRestoreTemplates(){
 try{const templates=JSON.parse(localStorage.getItem('teh-positive-templates-v1')||'[]');const el=document.getElementById('positiveTemplates');if(el&&Array.isArray(templates))el.value=templates.join('\\n')}catch(e){}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',positiveRestoreTemplates);
else positiveRestoreTemplates();


</script>"""
s = s.replace('</body>', positive_script + '</body>', 1)

# Independent recovery runs even when the main positive-reviews script fails.
# Never overwrite or remove stored templates, review data, or attempt journal.
positive_recovery_script = """<script>
(function(){
 function restorePositiveSavedData(){
  const dayInput=document.getElementById('positiveDay');
  const templatesInput=document.getElementById('positiveTemplates');
  if(!dayInput||!templatesInput)return;
  try{
   const raw=localStorage.getItem('teh-positive-templates-v1');
   if(raw&&!templatesInput.value){
    const templates=JSON.parse(raw);
    if(Array.isArray(templates))templatesInput.value=templates.join('\\n');
   }
  }catch(e){}
  try{
   const dates=[];
   for(let i=0;i<localStorage.length;i++){
    const key=localStorage.key(i)||'';
    const match=/^teh-positive-v2:(\\d{4}-\\d{2}-\\d{2})$/.exec(key);
    if(match)dates.push(match[1]);
   }
   dates.sort();
   if(!dayInput.value&&dates.length)dayInput.value=dates[dates.length-1];
   if(dayInput.value&&typeof positiveRender==='function'){
    positiveRender(dayInput.value);
   }else if(dayInput.value){
    const status=document.getElementById('positiveStatus');
    if(status)status.textContent='⚠️ Збережені відгуки знайдено, але інтерфейс не завантажився. Не очищуйте дані браузера.';
   }
  }catch(e){
   const status=document.getElementById('positiveStatus');
   if(status)status.textContent='⚠️ Не вдалося відобразити збережені відгуки: '+String(e.message||e);
  }
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',restorePositiveSavedData);
 else restorePositiveSavedData();
})();
</script>"""
s = s.replace('</body>', positive_recovery_script + '</body>', 1)

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
loaders += '<script src="ttn.js?v=2"></script><script src="boss-dashboard.js?v=4"></script>'
# Keep the negative-review process polling until a confirmed terminal state.
s = s.replace("setStatus(id,d.status==='started'?'running':'busy','⏳ '+d.message)}catch(e){setStatus(id,'error','❌ '+e.message)}}async function runOrderCount()",
"""setStatus(id,d.status==='started'?'running':'busy','⏳ '+d.message);if(d.status==='started'){clearInterval(timers[id]);timers[id]=setInterval(async()=>{try{const state=await jf(API+'/negative/status');if(state.status==='running')setStatus(id,'running','⏳ '+state.message);else if(state.status==='success'||state.status==='error'){clearInterval(timers[id]);setStatus(id,state.status,(state.status==='success'?'✅ ':'❌ ')+state.message)}}catch(e){clearInterval(timers[id]);setStatus(id,'error','❌ '+e.message)}},2000)}}catch(e){setStatus(id,'error','❌ '+e.message)}}async function runOrderCount()""",1)

# Read-only diagnostics for the negative reviews integrations.
negative_diagnostic_controls = '''<div class="card" style="margin-top:16px"><h3>Перевірка підключень</h3><p>Google-таблиця, аркуші, активні магазини та авторизація Prom. Без запису даних.</p><button class="run" onclick="checkNegativeConnections(this)">🔎 Перевірити підключення</button> <button class="run" type="button" onclick="checkReviewReadProbe(this)">📖 Перевірити читання відгуків</button> <button class="run" type="button" onclick="checkPromReviewsHttp(this)">🌐 Перевірити відгуки через HTTP (без браузера)</button> <button class="run" type="button" onclick="checkPromContextJson(this)">🧪 Перевірити JSON відгуків</button> <button class="run" type="button" onclick="checkPromCompanyList(this)">📄 Перевірити сторінки компанії (POST)</button> <button class="run" type="button" onclick="showPromConnectionGuide(this)">🔐 Підключити Prom</button><div class="status promConnectionGuide" style="display:none;white-space:normal;margin-top:12px"><strong>Підключення головного акаунта Prom</strong><p>1. Відкрийте офіційний кабінет Prom і увійдіть у головний акаунт.</p><p>2. Офіційний публічний API Prom не документує отримання відгуків про компанію та товари, потрібних цим вигрузкам. Створення API-токена поки не допоможе.</p><p>3. Вхід у браузері не передає сесію Chromium на Render. Сервер має отримати окрему захищену авторизацію; автоматичне підключення ще не реалізоване. Не надсилайте логін, пароль, токен або cookies у чат.</p><a href="https://my.prom.ua/cms/" target="_blank" rel="noopener noreferrer">Відкрити офіційний кабінет Prom ↗</a><p><strong>Статус:</strong> серверну авторизацію ще не підтверджено.</p></div><div class="status negativeDiagnosticResult" style="white-space:pre-wrap">Перевірка ще не запускалася.</div><div class="status reviewReadProbeResult" style="white-space:pre-wrap">Читання відгуків ще не перевірялося.</div><div class="status promReviewsHttpResult" style="white-space:pre-wrap">HTTP-перевірка ще не запускалася.</div><div class="status promContextJsonResult" style="white-space:pre-wrap">JSON-перевірка ще не запускалася.</div><div class="status promCompanyListResult" style="white-space:pre-wrap">POST-перевірка ще не запускалася.</div><button class="run" type="button" onclick="checkNegativeSystemHealth(this)">🩺 Перевірити стан Render (без браузера)</button><div class="status negativeSystemHealthResult" style="white-space:pre-wrap">Моніторинг ще не запускався.</div></div>'''
for view_id in ('negative-reviews', 'negative-analytics'):
    start = s.find('<section class="view" id="' + view_id + '">')
    if start >= 0:
        end = s.find('</section>', start)
        if end >= 0:
            s = s[:end] + negative_diagnostic_controls + s[end:]

negative_diagnostic_script = '''<script>
async function checkPromCompanyList(button){
 const out=button.closest(".card").querySelector(".promCompanyListResult");
 button.disabled=true;out.textContent="⏳ Перевіряємо POST /list, сторінки 1 і 2…";
 try{
  const response=await fetch("/api/negative/http-company-list-probe",{cache:"no-store"});
  if(!response.ok)throw Error("HTTP "+response.status);
  const d=await response.json();
  if(d.status!=="ok")throw Error(d.message||"Помилка POST-перевірки");
  out.textContent=[
   "POST /cms/opinions/company/list:",
   ...(d.results||[]).map(x=>"Сторінка "+x.page_requested+": "+(x.error||("HTTP "+x.http+", "+x.content_type+", ключі ["+(x.top_level_keys||[]).join(", ")+"]"+", context ["+(x.context_keys||[]).join(", ")+"]"+", data "+(x.data_type||"—")+" ["+(x.data_keys||[]).join(", ")+"]"+", відгуків "+(x.opinions_count??"—")+", негативних "+(x.negative_count??"—")+", current_page "+(x.pagination?.current_page??"—")+", перший ID "+(x.first_opinion_id??"—")+", відбиток "+(x.response_fingerprint??"—")))),
   ...(d.results||[]).map(x=>"Сторінка "+x.page_requested+" — HTTP-діагностика: Cloudflare challenge="+(x.cf_mitigated?"так":"ні")+", CF-Ray="+(x.cf_ray_present?"так":"ні")+", server="+(x.server_class||"—")+", CSRF-cookie="+(x.csrf_cookie_present?"є":"немає")+", CSRF-header="+(x.csrf_header_sent?(x.csrf_header_kind||"надіслано"):"не надіслано")+", WWW-Authenticate="+(x.www_authenticate_present?"є":"немає")+", redirect="+(x.redirect_present?"так":"ні")),
   "Відповіді відрізняються: "+(d.different_responses?"✅ так":"⚠️ ні / не вдалося перевірити"),
   d.note||""
  ].join("\\n");
 }catch(e){out.textContent="❌ "+e.message}
 finally{button.disabled=false}
}
async function checkPromContextJson(button){
 const out=button.closest(".card").querySelector(".promContextJsonResult");
 button.disabled=true;out.textContent="⏳ Читаємо JSON відгуків через HTTP…";
 try{
  const response=await fetch("/api/negative/http-context-probe",{cache:"no-store"});
  if(!response.ok)throw Error("HTTP "+response.status);
  const d=await response.json();
  if(d.status!=="ok")throw Error(d.message||"Не вдалося перевірити JSON");
  out.textContent=[
   "JSON-відгуки Prom (без Chromium):",
   ...(d.results||[]).map(x=>x.type+" сторінка "+x.page+": "+(x.error||("HTTP "+x.http+", JSON "+(x.json_ok?"OK":"не підтверджено")+", відгуків "+(x.opinions_count??"—")+", негативних "+(x.negative_count??"—")+", магазин ID "+(x.company_ids||[]).join(", ")+", сторінок "+(x.pagination?.num_pages??"—")))),
   ...(d.results||[]).map(x=>x.type+" стор. "+x.page+" — структура: status="+(x.status_value??"—")+", ключі "+(x.top_level_keys||[]).join("/")+", context "+x.context_type+" ["+(x.context_keys||[]).join(", ")+"]"+", opinions="+x.opinions_type+", pagination="+x.pagination_type+", bytes="+(x.response_bytes??"—")+", code="+(x.error_code??"—")),
   ...(d.results||[]).map(x=>x.type+" стор. "+x.page+" — pagination.current_page="+(x.pagination?.current_page??"—")+", first_opinion_id="+(x.first_opinion_id??"—")+", fingerprint="+(x.response_sha256_short??"—")),
   "Однакова відповідь company 1/2: "+(d.company_response_same?"так":"ні"),
   "Однакова відповідь product 1/2: "+(d.product_response_same?"так":"ні"),
   "Пагінація сторінок 1 і 2: "+(d.pagination_verified?"✅ підтверджена":"⚠️ не підтверджена"),
   d.note||""
  ].join("\\n");
 }catch(e){out.textContent="❌ "+e.message}
 finally{button.disabled=false}
}
async function checkPromReviewsHttp(button){
 const out=button.closest(".card").querySelector(".promReviewsHttpResult");
 button.disabled=true;out.textContent="⏳ Перевіряємо HTTP-доступ без Chromium…";
 try{
  const response=await fetch("/api/negative/http-reviews-probe",{cache:"no-store"});
  if(!response.ok)throw Error("HTTP "+response.status);
  const d=await response.json();
  if(d.status!=="ok"){out.textContent="❌ "+(d.message||"Помилка HTTP-перевірки");return}
  out.textContent=[
   "🌐 HTTP-перевірка завершена",
   ...(d.results||[]).map(x=>x.type+": "+(x.error||("HTTP "+x.http+", "+x.content_type+", HTML-маркери відгуків: "+(x.review_markup?"так":"ні")+", форма входу: "+(x.login_markup?"так":"ні")+", redirect: "+x.redirect))),
   ...(d.results||[]).map(x=>{
     const h=x.html_structure;
     if(!h)return x.type+": структура недоступна";
     return x.type+" — структура HTML: скриптів "+h.scripts_total+" (зовнішніх "+h.scripts_external+"), JSON-скриптів "+h.json_scripts+
       "; Next/Nuxt/State: "+[h.next_state,h.nuxt_state,h.initial_state].map(v=>v?"так":"ні").join("/")+
       "; згадки відгуків/API/магазину/кабінету: "+[h.review_terms,h.api_terms,h.shop_terms,h.cabinet_terms].map(v=>v?"так":"ні").join("/")+
       (h.html_truncated?"; перевірено лише перші 120 КБ":"");
   }),
   ...(d.results||[]).map(x=>{
     const h=x.html_structure||{},a=h.auth_hints||{};
     return x.type+" — авторизація (ознаки, не підтвердження): ID магазину "+(a.shop_id_pattern?"є":"немає")+
       ", перемикач "+(a.shop_selector?"є":"немає")+", вихід "+(a.logout_marker?"є":"немає")+
       ", маршрут відгуків "+(a.review_route_marker?"є":"немає")+
       "; пропущено зовнішніх скриптів "+(h.excluded_script_tags??"—")+
       " з "+(h.external_script_hosts_count??"—")+" інших доменів";
   }),
   ...(d.results||[]).map(x=>{
     const c=x.cookie_comparison||{};
     return x.type+" — порівняння із запитом без cookies: HTTP "+(c.anonymous_http??"помилка")+
       ", HTML "+(c.same_markup===true?"однаковий":c.same_markup===false?"відрізняється":"не вдалося порівняти")+
       ", схожість "+(c.similarity_percent??"—")+"%";
   }),
   "HTML сторінок компанії та товарів: "+(d.html_identical?"однаковий":"відрізняється або порівняння недоступне"),
   ...(d.results||[]).map(x=>{
     const j=x.html_structure?.js_scan;
     return j ? x.type+" — JS-файли: доступних "+j.eligible_assets+", перевірено "+j.checked+
       ", зі згадками відгуків "+j.review_assets+
       ", API "+j.api_assets+
       ", fetch/axios "+j.fetch_assets+
       ", відгуки+API "+j.review_api_assets+
       ", помилок "+j.errors : x.type+" — JS-перевірка недоступна";
   }),
   "⚠️ "+d.note
  ].join("\\n");
 }catch(e){out.textContent="❌ "+e.message}
 finally{button.disabled=false}
}
async function checkNegativeSystemHealth(button){
 const out=button.closest(".card").querySelector(".negativeSystemHealthResult");
 button.disabled=true;out.textContent="⏳ Отримуємо стан сервера без запуску браузера…";
 try{
  const response=await fetch("/api/negative/system-health",{cache:"no-store"});
  if(!response.ok)throw Error("HTTP "+response.status);
  const d=await response.json(),m=d.memory_cgroup||{},p=d.probe||{};
  const mb=x=>Number.isFinite(x)?(x/1048576).toFixed(0)+" МБ":"не визначено";
  out.textContent=[
   "Стан: "+d.status,
   "Пам’ять контейнера: "+mb(m.used_bytes)+" / "+mb(m.limit_bytes),
   "Пам’ять Flask: "+d.worker_rss_mb+" МБ",
   "Chromium: "+d.chromium_count+" процесів, "+d.chromium_rss_mb+" МБ",
   "Час роботи системи: "+Math.round((d.system_uptime_seconds||0)/60)+" хв",
   "ID запуску системи: "+(d.instance_boot_id||"невідомо"),
   "Останній тест: "+(p.status||"невідомо")+" / "+(p.stage||p.message||"—"),
   "Події пам’яті: "+(m.events||"недоступні"),
   "— Заміри останнього тесту —",
   ...((d.probe_metrics||[]).length ? [
     "Кількість замірів: "+d.probe_metrics.length,
     "Пік пам’яті: "+Math.max(...d.probe_metrics.map(x=>x.memory_mb||0)).toFixed(1)+" МБ",
     "Пік процесів Chromium: "+Math.max(...d.probe_metrics.map(x=>x.chromium||0)),
     ...d.probe_metrics.slice(-12).map(x=>x.seconds+" с: "+(x.memory_mb??"—")+" МБ, Chromium "+x.chromium)
   ] : ["Замірів ще немає"])
  ].join("\\n");
 }catch(e){out.textContent="❌ Не вдалося отримати стан сервера: "+e.message}
 finally{button.disabled=false}
}
async function checkReviewReadProbe(button){
 const out=button.closest(".card").querySelector(".reviewReadProbeResult");
 button.disabled=true;
 out.textContent="⏳ Запускаємо окрему перевірку читання одного магазину…";
 try{
  let response=await fetch("/api/negative/review-probe",{method:"POST"});
  let data=await response.json();
  if(!response.ok)throw Error(data.message||"HTTP "+response.status);
  for(let i=0;i<45;i++){
   await new Promise(resolve=>setTimeout(resolve,5000));
   response=await fetch("/api/negative/review-probe/status",{cache:"no-store"});
   if(!response.ok)throw Error("Сервер тимчасово недоступний (HTTP "+response.status+"). Не запускайте тест повторно.");
   data=await response.json();
   if(data.status!=="running")break;
   out.textContent="⏳ "+(data.stage||"Перевірка триває")+"\\n"+(data.shop||"")+"\\nДані не змінюються.";
  }
  if(data.status==="running"){out.textContent="⚠️ Тест ще триває. Не запускайте його повторно.";return}
  if(data.status==="error"){out.textContent="❌ "+(data.message||"Не вдалося перевірити читання");return}
  if(data.status==="success"){out.textContent=(data.ok?"✅ Читання підтверджено":"⚠️ Читання підтверджено не повністю")+"\\nМагазин: "+(data.shop||"")+"\\n"+(data.results||[]).map(x=>(x.ok?"✅ ":"❌ ")+x.type+": "+x.message).join("\\n");return}
  out.textContent="⚠️ Статус тесту невідомий. Не запускайте його повторно.";
 }catch(error){out.textContent="❌ "+error.message}
 finally{button.disabled=false}
}
function showPromConnectionGuide(button){const guide=button.closest(".card").querySelector(".promConnectionGuide");guide.style.display=guide.style.display==="none"?"block":"none";}
async function checkNegativeConnections(button){
 const panel=button.closest(".card"),out=panel.querySelector(".negativeDiagnosticResult");
 button.disabled=true;out.textContent="⏳ Запускаємо перевірку Google Sheets і Prom...";
 try{
  let response=await fetch("/api/negative/diagnostic",{method:"POST"});
  let raw=await response.text(),data;
  try{data=JSON.parse(raw)}catch(_){throw Error("HTTP "+response.status+" · "+(raw?"неочікувана відповідь":"порожня відповідь"))}
  if(!response.ok)throw Error("HTTP "+response.status+" · "+(data.message||"Помилка сервера"));
  for(let i=0;data.status==="running"&&i<8;i++){
   out.textContent="⏳ Перевірка триває… "+(i*3)+" с. Дані не змінюються.";
   await new Promise(resolve=>setTimeout(resolve,15000));
   response=await fetch("/api/negative/diagnostic/status",{cache:"no-store"});
   raw=await response.text();
   if(response.status===429){out.textContent="⏳ Сервер тимчасово обмежує запити (429). Зачекайте, перевірку не запускаємо повторно.";continue}
   try{data=JSON.parse(raw)}catch(_){throw Error("HTTP "+response.status+" · не вдалося прочитати статус")}
  }
  if(data.status==="running"){out.textContent="⚠️ Перевірка перевищила 2 хвилини. Останній етап: "+(data.stage||"невідомий")+"\\n"+(data.checks||[]).map(c=>(c.ok?"✅ ":"❌ ")+c.name+": "+c.message).join("\\n")+"\\nНе запускайте перевірку повторно.";return}
  if(data.status==="idle")throw Error("Render повернув порожній стан перевірки (idle). Можливо, запити потрапили в різні процеси сервера.");
  if(!Array.isArray(data.checks)||!data.checks.length)throw Error("Render не повернув результати перевірки. Статус: "+String(data.status||"невідомий")+".");
  if(data.status==="error")throw Error(data.message||"Помилка перевірки");
  out.textContent=(data.ok?"✅ Підключення працюють":"⚠️ Потрібна увага")+"\\n"+(data.checks||[]).map(c=>(c.ok?"✅ ":"❌ ")+c.name+": "+c.message).join("\\n");
 }catch(error){out.textContent="❌ "+error.message}
 finally{button.disabled=false}
}
</script>'''
s = s.replace('</body>', negative_diagnostic_script + '</body>', 1)

pos = s.rfind('<script>')
if pos < 0:
    raise SystemExit('Main frontend script not found')
s = s[:pos] + loaders + s[pos:]

p.write_text(s, encoding='utf-8')
print('Cloudflare frontend validated; training, database and role access views are ready.')