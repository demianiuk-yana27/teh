/**
 * Windows Quick Requests -> Google Sheets.
 * Deploy as a Web app: execute as Me; access Anyone.
 * Set Script Properties: QUICK_REQUESTS_KEY (48+ random chars).
 * Never put Google credentials into the Windows executable.
 */
const BOOKS = {
  requests: '1gojVDMKs3-6NuC6vdVDHy3P_OnY_G89NXIn_FAEFV3I',
  ttn: '1GUOFW957ijYV9KOhC61xTS22aL5vhWj6JUI7gQi__-o'
};
const SHEETS = ['2 Відділ','Тех','Опт/дроп'];
const TAGS = {
  '2 Відділ':['Інше','На вайбер (месенджери)','Оформити','Рахунок/ додаткові дії','Цікавить/консультація','ОПТ собі'],
  'Тех':['Інше','Оф чати геткол','Обʼєднання замовлень','Питання по замовленню','Дооформити розетка','Пропущений','Бот приїхала']
};
const ERRORS=['Менеджера','Прохання клієнта','Нічия'];
const CHANGES=['Зміна суми наложки','Зняття наложки','Повернення посилки','Зміна отримувача','Оплата доставки/Зміна платника','Переадресація','Продовжити термін зберігання','Скасувати повернення','Зміна номера'];

function output_(data) {
  return ContentService.createTextOutput(JSON.stringify(data)).setMimeType(ContentService.MimeType.JSON);
}
function secureEqual_(a,b) {
  a=String(a||''); b=String(b||'');
  if (a.length !== b.length || b.length < 32) return false;
  let mismatch=0;
  for (let i=0;i<a.length;i++) mismatch |= a.charCodeAt(i)^b.charCodeAt(i);
  return mismatch===0;
}
function doGet() {
  return output_({ok:true,service:'TehQuickRequests',version:1});
}
function doPost(e) {
  try { return output_(submit_(JSON.parse(e.postData.contents))); }
  catch (error) { return output_({ok:false,error:String(error.message||error)}); }
}
function submit_(body) {
  if (!body || typeof body !== 'object') throw Error('Некоректний запит');
  const expected=PropertiesService.getScriptProperties().getProperty('QUICK_REQUESTS_KEY');
  if (!secureEqual_(body.key,expected)) throw Error('Невірний ключ програми');
  const mode=body.mode, tab=body.tab;
  if (mode!=='requests' && mode!=='ttn') throw Error('Невірний режим');
  if (mode==='requests' && SHEETS.indexOf(tab)<0) throw Error('Невірна вкладка');
  const values=Array.isArray(body.values)?body.values.map(x=>String(x===null||x===undefined?'':x).trim()):[];
  if (values.length !== (mode==='ttn'?6:4) || values.some(x=>!x||x.length>2000)) throw Error('Заповніть усі обов’язкові поля');
  if (mode==='requests' && tab==='Опт/дроп' && ['Опт','Дроп'].indexOf(values[1])<0) throw Error('Невірний тип запиту');
  if (mode==='requests' && tab!=='Опт/дроп' && TAGS[tab].indexOf(values[3])<0) throw Error('Невірна мітка');
  if (mode==='ttn' && (ERRORS.indexOf(values[4])<0 || CHANGES.indexOf(values[5])<0)) throw Error('Невірна категорія зміни');
  const requestId=String(body.requestId||'');
  if (!/^[a-f0-9-]{32,36}$/i.test(requestId)) throw Error('Некоректний ID запиту');
  const lock=LockService.getScriptLock();
  if (!lock.tryLock(25000)) throw Error('Таблиця зайнята. Повторіть запит через кілька секунд');
  try {
    const cache=CacheService.getScriptCache();
    const cacheKey='request_'+requestId.replace(/-/g,'');
    const previous=cache.get(cacheKey);
    if (previous) return JSON.parse(previous);
    const sheetName=mode==='ttn'?'Зміни з ТТН':tab;
    const sheet=SpreadsheetApp.openById(BOOKS[mode]).getSheetByName(sheetName);
    if (!sheet) throw Error('Не знайдено вкладку '+sheetName);
    const now=new Date();
    const dateValue=Utilities.formatDate(now,'Europe/Kyiv',mode==='ttn'?'yyyy-MM-dd':'dd.MM. HH:mm');
    const rowValues=[dateValue].concat(values);
    let target;
    if (mode==='requests' && tab==='Тех') {
      // B is mandatory and has no gaps, including historical records.
      const last=sheet.getLastRow();
      // B is contiguous. Check the tail first instead of downloading all historical rows.
      // Other columns may extend below B, so scan backward in small blocks if needed.
      let lastFilled=1;
      for (let end=last;end>=2;end-=128) {
        const start=Math.max(2,end-127);
        const column=sheet.getRange(start,2,end-start+1,1).getDisplayValues();
        for (let i=column.length-1;i>=0;i--) {
          if (String(column[i][0]||'').trim()) {
            lastFilled=start+i;
            break;
          }
        }
        if (lastFilled>1) break;
      }
      target=lastFilled+1;
      if (target>12000) throw Error('Не знайдено вільного рядка у вкладці Тех');
      if (target>sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(),target-sheet.getMaxRows());
      sheet.getRange(target,1,1,5).setNumberFormat('@').setValues([rowValues]);
    } else {
      // Insert below last occupied row; preserve existing headers and values.
      target=Math.max(2,sheet.getLastRow()+1);
      if (target>sheet.getMaxRows()) sheet.insertRowsAfter(sheet.getMaxRows(),target-sheet.getMaxRows());
      sheet.getRange(target,1,1,rowValues.length).setNumberFormat('@').setValues([rowValues]);
    }
    SpreadsheetApp.flush();
    const actual=sheet.getRange(target,1,1,rowValues.length).getDisplayValues()[0];
    const matches=actual.every((x,i)=>String(x).trim()===String(rowValues[i]).trim());
    const range=sheetName+'!A'+target+':'+(mode==='ttn'?'G':'E')+target;
    const result=matches?
      {ok:true,sheetName,updatedRange:range}:
      {ok:false,unverified:true,sheetName,updatedRange:range,message:'Запис виконано, але перевірка значень не збіглася. Перевірте таблицю перед повтором.'};
    cache.put(cacheKey,JSON.stringify(result),21600);
    return result;
  } finally {
    lock.releaseLock();
  }
}
