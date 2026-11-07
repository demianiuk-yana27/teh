// Deploy under marketonlajn@gmail.com as Web App, execute as Me.
// Script Properties: TTN_API_SECRET (random secret, same as Cloudflare), no secrets in source.
const SHEET_ID='1GUOFW957ijYV9KOhC61xTS22aL5vhWj6JUI7gQi__-o';
const SHEET_GID=1184410012;
const RECIPIENT='rjprofy1619@gmail.com';
const LABELS={
 'Зміна суми наложки':['змінити суму накладеного платежу на',true],
 'Зняття наложки':['зняти накладений платіж',false],
 'Зміна отримувача':['змінити отримувача на',true],
 'Оплата доставки чи зміна платника':['зробити доставку за наш рахунок',false],
 'Оплата доставки/Зміна платника':['зробити доставку за наш рахунок',false],
 'Переадресація':['зробити переадресацію у',true],
 'Зміна номера':['змінити номер отримувача на',true],
 'Зміна Номера':['змінити номер отримувача на',true]
};
const BOGDAN=['Продовжити термін зберігання','Скасувати повернення'];
function response_(x){return ContentService.createTextOutput(JSON.stringify(x)).setMimeType(ContentService.MimeType.JSON)}
function sheet_(){const book=SpreadsheetApp.openById(SHEET_ID);const sh=book.getSheets().find(x=>x.getSheetId()===SHEET_GID);if(!sh)throw Error('Вкладку не знайдено');return sh}
function type_(x){return String(x||'').trim()}
function draft_(type,ttn,detail){
 const t=LABELS[type];if(!t)throw Error('Для цього типу лист не передбачено');
 if(!/^\d{8,20}$/.test(ttn))throw Error('Перевірте номер ТТН');
 if(t[1]&&!detail)throw Error('Потрібні додаткові дані');
 return 'Доброго дня! '+ttn+' - потрібно '+t[0]+(t[1]?' '+detail:'')+'.';
}
function doPost(e){
 const lock=LockService.getScriptLock();
 try{
  const b=JSON.parse(e.postData.contents||'{}');
  if(!b.secret||b.secret!==PropertiesService.getScriptProperties().getProperty('TTN_API_SECRET'))return response_({ok:false,error:'Немає доступу'});
  if(!lock.tryLock(10000))return response_({ok:false,error:'Спробуйте повторити через кілька секунд'});
  const sh=sheet_(),last=sh.getLastRow();
  if(b.action==='list'){
   if(last<2)return response_({ok:true,items:[]});
   const rows=sh.getRange(2,1,last-1,10).getDisplayValues();
   const items=rows.map((v,i)=>({row:i+2,date:v[0],author:v[1],order:v[2],ttn:v[3],description:v[4],extra:v[5],type:v[6],status:v[7],executor:v[9]}))
    .filter(x=>!x.status.trim()&&!x.executor.trim()&&(x.ttn||x.type||x.description));
   return response_({ok:true,items});
  }
  if(b.action!=='process'||!Number.isInteger(b.row)||b.row<2||b.row>last)return response_({ok:false,error:'Некоректний запит'});
  const v=sh.getRange(b.row,1,1,10).getDisplayValues()[0];
  if(v[7].trim()||v[9].trim())return response_({ok:false,error:'Запит уже взято в роботу. Оновіть список.'});
  const manager=String(b.manager||''),operation=b.operation,type=type_(v[6]),ttn=type_(v[3]);
  if(!['Яна','Наталя'].includes(manager))return response_({ok:false,error:'Оберіть виконавця'});
  if(operation==='impossible'){
   const reason=String(b.detail||'').trim();
   if(!reason)return response_({ok:false,error:'Вкажіть причину неможливості виконання'});
   sh.getRange(b.row,8).setValue('Неможливо виконати');
   sh.getRange(b.row,9).setNumberFormat('@').setValue(reason);
   sh.getRange(b.row,10).setValue(manager);
   return response_({ok:true});
  }else if(operation==='bogdan'){
   // Assignment only: leave status (H) and processing date (I) untouched.
   sh.getRange(b.row,10).setValue('Богдан');
   return response_({ok:true});
  }else if(operation==='return'&&type==='Повернення посилки'){
   sh.getRange(b.row,8).setValue('Виконано');
   sh.getRange(b.row,10).setValue(manager);
  }else if(operation==='send'&&LABELS[type]&&!BOGDAN.includes(type)){
   const detail=String(b.detail||'').trim();
   const body=draft_(type,ttn,detail);
   // Never write an intermediate status: column H has strict dropdown validation.
   // Lock prevents concurrent managers processing the same row during this operation.
   GmailApp.sendEmail(RECIPIENT,'',body,{name:'Технічний відділ'});
   sh.getRange(b.row,8).setValue('В роботі');
   sh.getRange(b.row,10).setValue(manager);
  }else return response_({ok:false,error:'Ця дія недоступна для обраного типу'});
  sh.getRange(b.row,9).setValue(new Date()).setNumberFormat('dd.MM.yyyy');
  return response_({ok:true});
 }catch(err){return response_({ok:false,error:String(err.message||err)})}
 finally{if(lock.hasLock())lock.releaseLock()}
}
