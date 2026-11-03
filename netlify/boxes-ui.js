(()=>{
const RULES={
 'Нова пошта':{
  '1 товар':{
   'Звичайне':{places:'Залишаємо ті розміри, які тягнуть місця.',box:'Не додаємо',pack:'Додаємо окремим артикулем'},
   'Гофра':{places:'Залишаємо ті розміри, які тягнуть місця.',box:'Не додаємо',pack:'Додаємо окремим артикулем'},
   'Стрейч':{places:'Залишаємо ті розміри, які тягнуть місця.',box:'Не додаємо',pack:'Додаємо окремим артикулем + 10 грн за стрейч'}
  },
  '3+ товари':{
   'Звичайне':{places:"Об'ємна вага — з підбору коробки. Все інше 10 / 10 / 10.",box:'Додаємо',pack:'Вартість пакету додаємо до вартості коробки'},
   'Гофра':{places:"Об'ємна вага — з підбору коробки. Все інше — фактичні габарити, які показує підбір коробки.",box:'Додаємо гофру',pack:'Вартість пакету додаємо до вартості гофри'},
   'Стрейч':{places:"Об'ємна вага — з підбору коробки. Все інше — фактичні габарити, які показує підбір коробки.",box:'Не додаємо',pack:'Додаємо окремим артикулем + 10 грн за стрейч'}
  }
 },
 'Укрпошта':{
  '1 товар':{
   'Звичайне':{places:'Фактична вага, фактичні габарити коробки з сайту підбору',box:'Не додаємо',pack:'Додаємо окремим артикулем'},
   'Гофра':{places:'Фактична вага, фактичні габарити коробки з сайту підбору',box:'Не додаємо',pack:'Додаємо окремим артикулем'},
   'Стрейч':{places:'Фактична вага, фактичні габарити коробки з сайту підбору',box:'Не додаємо',pack:'Додаємо окремим артикулем + 10 грн за стрейч'}
  },
  '3+ товари':{
   'Звичайне':{places:'Фактична вага, фактичні габарити коробки з сайту підбору',box:'Додаємо',pack:'Вартість пакету додаємо до вартості коробки'},
   'Гофра':{places:'Фактична вага, фактичні габарити коробки з сайту підбору',box:'Додаємо гофру',pack:'Вартість пакету додаємо до вартості гофри'},
   'Стрейч':{places:'Фактична вага, фактичні габарити коробки з сайту підбору',box:'Не додаємо',pack:'Додаємо окремим артикулем + 10 грн за стрейч'}
  }
 }
};
const EXTRA=[
 ['✂️ Підрізані коробки','Об’ємну вагу обираємо завжди менше значення, а коробку додаємо за більшим значенням.','Сайт підбирає 10 кг, підрізана до 5 кг → додаємо в CRM коробку 10 кг, але об’ємну вагу зазначаємо 5 кг.'],
 ['⚖️ Фактична вага більша об’ємної','Якщо фактична вага більша об’ємної — пишемо фактичну.','Сайт пропонує коробку 10, підрізана до 7 кг, але фактична вага товару 15 кг → об’ємну пишемо 15 кг.'],
 ['💳 Prom-оплата з АПС','Якщо в замовленні є АПС і воно оплачено на Prom — коробку не додаємо.',''],
 ['📐 У CRM та підборі немає розмірів','Підбираєте в GPT орієнтовні розміри. Якщо немає — пишете 1 / 10 / 10 / 10 і обов’язково в коментарі менеджера: «розміри приблизні».',''],
 ['📦 Габаритний товар і сайт не підтягнув пакування','Пишемо запит у чат складу щодо коробки зі скріншотом того, що показав підбір коробки, та лінком на сторінку підбору коробки.','Склад може відповісти, наприклад: «гофра 20 кг». Тоді додаємо гофру в корзину, а в місцях прописуємо: 20 / 10 / 10 / 10.']
];
function renderResult(){const d=document.getElementById('boxDelivery'),q=document.getElementById('boxQty'),p=document.getElementById('boxPack');if(!d||!q||!p)return;const r=RULES[d.value][q.value][p.value];document.getElementById('boxPlaces').textContent=r.places;document.getElementById('boxBox').textContent=r.box;document.getElementById('boxPackage').textContent=r.pack;}
function init(){const root=document.getElementById('boxesApp');if(!root)return;root.innerHTML=`<div class="box-helper"><p>Оберіть три умови нижче — інструкція оновиться автоматично.</p><div class="box-pickers"><label><span>1 · Спосіб доставки</span><select id="boxDelivery"><option>Нова пошта</option><option>Укрпошта</option></select></label><label><span>2 · Кількість товарів</span><select id="boxQty"><option>1 товар</option><option>3+ товари</option></select></label><label><span>3 · Пакування</span><select id="boxPack"><option>Звичайне</option><option>Гофра</option><option>Стрейч</option></select></label></div><h3>ВАША ІНСТРУКЦІЯ</h3><div class="box-results"><article><b>① МІСЦЯ · ВАГА ТА ГАБАРИТИ</b><div id="boxPlaces"></div></article><article><b>② КОРОБКА / ГОФРА</b><div id="boxBox"></div></article><article><b>③ ПАКЕТ ТА ДОДАТКОВА ВАРТІСТЬ</b><div id="boxPackage"></div></article></div><div class="box-hint">💡 Змінюйте лише три поля зверху — результат перераховується одразу.</div></div><h3 class="box-extra-title">📌 Додаткові правила</h3><div class="box-extra">${EXTRA.map(x=>`<article><h4>${x[0]}</h4><p>${x[1]}</p>${x[2]?`<div class="box-example"><b>Приклад:</b> ${x[2]}</div>`:''}</article>`).join('')}</div>`;['boxDelivery','boxQty','boxPack'].forEach(id=>document.getElementById(id).onchange=renderResult);renderResult();}
function styles(){if(document.getElementById('boxesStyles'))return;const s=document.createElement('style');s.id='boxesStyles';s.textContent=`.training-child{margin-left:34px!important;font-size:13px!important}.box-helper{background:#fff;border:1px solid #dce6f3;border-radius:18px;padding:22px;box-shadow:0 8px 24px #17385e0a}.box-helper>p{color:#7184a2;margin:0 0 20px}.box-pickers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.box-pickers label{display:flex;flex-direction:column;gap:7px;font-weight:800;color:#45607f}.box-pickers select{width:100%;border:2px solid #f0c84d;background:#fffbea;border-radius:11px;padding:12px;font:inherit;color:#142746}.box-helper h3{margin:25px 0 12px}.box-results{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.box-results article{border:1px solid #d6e2f1;border-radius:13px;background:#f8fbff;padding:16px;min-height:145px}.box-results b{display:block;color:#31577e;margin-bottom:12px}.box-results article div{line-height:1.55;font-size:16px}.box-hint{margin-top:15px;padding:12px 14px;border-radius:10px;background:#fff8df;color:#745b13}.box-extra-title{margin:24px 0 12px}.box-extra{display:grid;gap:12px}.box-extra article{background:#fff;border:1px solid #dce6f3;border-radius:14px;padding:17px 18px;box-shadow:0 5px 16px #17385e08}.box-extra h4{margin:0 0 8px;font-size:16px}.box-extra p{margin:0;line-height:1.6}.box-example{margin-top:10px;padding:10px 12px;background:#f2f7ff;border-radius:9px;line-height:1.55}@media(max-width:850px){.box-pickers,.box-results{grid-template-columns:1fr}}`;document.head.appendChild(s)}
window.addEventListener('DOMContentLoaded',()=>{styles();init()});
})();