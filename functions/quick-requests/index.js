const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
const BOOKS={requests:'1gojVDMKs3-6NuC6vdVDHy3P_OnY_G89NXIn_FAEFV3I',ttn:'1GUOFW957ijYV9KOhC61xTS22aL5vhWj6JUI7gQi__-o'};
const SHEETS=['2 Відділ','Тех','Опт/дроп'];
const TAGS={'2 Відділ':['Інше','На вайбер (месенджери)','Оформити','Рахунок/ додаткові дії','Цікавить/консультація','ОПТ собі'],'Тех':['Інше','Оф чати геткол','Обʼєднання замовлень','Питання по замовленню','Дооформити розетка','Пропущений','Бот приїхала']};
const ERROR_TYPES=['Менеджера','Прохання клієнта','Нічия'];
const CHANGE_TYPES=['Зміна суми наложки','Зняття наложки','Повернення посилки','Зміна отримувача','Оплата доставки/Зміна платника','Переадресація','Продовжити термін зберігання','Скасувати повернення','Зміна номера'];
const b64u=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');
async function googleToken(env){
 let sa;try{sa=JSON.parse(env.GOOGLE_SERVICE_ACCOUNT_JSON||'')}catch{throw Error('Невірний GOOGLE_SERVICE_ACCOUNT_JSON')}
 if(!sa.client_email||!sa.private_key)throw Error('Налаштуйте GOOGLE_SERVICE_ACCOUNT_JSON у Cloudflare Pages');
 const now=Math.floor(Date.now()/1000),enc=o=>b64u(new TextEncoder().encode(JSON.stringify(o)));
 const input=enc({alg:'RS256',typ:'JWT'})+'.'+enc({iss:sa.client_email,scope:'https://www.googleapis.com/auth/spreadsheets',aud:'https://oauth2.googleapis.com/token',iat:now,exp:now+3600});
 const pem=sa.private_key.replace(/-----BEGIN PRIVATE KEY-----|-----END PRIVATE KEY-----|\s/g,'');
 const raw=Uint8Array.from(atob(pem),c=>c.charCodeAt(0));
 const key=await crypto.subtle.importKey('pkcs8',raw,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['sign']);
 const sig=await crypto.subtle.sign('RSASSA-PKCS1-v1_5',key,new TextEncoder().encode(input));
 const body=new URLSearchParams({grant_type:'urn:ietf:params:oauth:grant-type:jwt-bearer',assertion:input+'.'+b64u(sig)});
 const r=await fetch('https://oauth2.googleapis.com/token',{method:'POST',body});const d=await r.json();if(!r.ok||!d.access_token)throw Error('Google OAuth: '+(d.error_description||d.error||r.status));return d.access_token;
}
async function google(token,book,range,method='GET',values){
 const url='https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(book)+'/values/'+encodeURIComponent(range)+(method==='PUT'?'?valueInputOption=USER_ENTERED':'?majorDimension=ROWS');
 const r=await fetch(url,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:values?JSON.stringify({majorDimension:'ROWS',values:[values]}):undefined});
 const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error?.message||'Google Sheets HTTP '+r.status);return d;
}
export async function onRequest({request,env,data}){
 if(!['boss','manager'].includes(data.role))return json({error:'Потрібен вхід на сайт.'},401);
 if(request.method!=='POST')return json({error:'Метод не підтримується'},405);
 if(!env.GOOGLE_SERVICE_ACCOUNT_JSON)return json({error:'Google Sheets ще не підключено. Потрібно додати секрет GOOGLE_SERVICE_ACCOUNT_JSON та надати сервісному акаунту доступ до таблиць.'},503);
 const b=await request.json().catch(()=>null);if(!b||typeof b!=='object')return json({error:'Некоректні дані'},400);
 const mode=b.mode,tab=b.tab;
 if(mode!=='requests'&&mode!=='ttn')return json({error:'Невірний режим'},400);
 if(mode==='requests'&&!SHEETS.includes(tab))return json({error:'Невірна вкладка'},400);
 const values=Array.isArray(b.values)?b.values.map(x=>String(x??'').trim()):[];
 if(values.some(x=>!x||x.length>2000)||values.length!==(mode==='ttn'?6:4))return json({error:'Заповніть усі обов’язкові поля'},400);
 if(mode==='requests'&&tab==='Опт/дроп'&&!['Опт','Дроп'].includes(values[1]))return json({error:'Невірний тип запиту'},400);
 if(mode==='requests'&&tab!=='Опт/дроп'&&!TAGS[tab].includes(values[3]))return json({error:'Невірна мітка'},400);
 if(mode==='ttn'&&(!ERROR_TYPES.includes(values[4])||!CHANGE_TYPES.includes(values[5])))return json({error:'Невірна категорія зміни'},400);
 const sheet=mode==='ttn'?'Зміни з ТТН':tab,book=BOOKS[mode],first=mode==='ttn'?'A':'B',last=mode==='ttn'?'G':'E';
 const today=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Kyiv'});
 const rowValues=mode==='ttn'?[today,...values]:values;
 try{
  const token=await googleToken(env);
  // append is atomic on the Sheets API side; no race between managers finding the next row.
  const range="'"+sheet.replace(/'/g,"''")+"'!"+first+'2:'+last;
  const url='https://sheets.googleapis.com/v4/spreadsheets/'+encodeURIComponent(book)+'/values/'+encodeURIComponent(range)+':append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS';
  const r=await fetch(url,{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({majorDimension:'ROWS',values:[rowValues]})});
  const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error?.message||'Google Sheets HTTP '+r.status);
  return json({ok:true,sheetName:sheet,updatedRange:d.updates?.updatedRange||''});
 }catch(e){console.error('Request submission failed',e);return json({error:'Не вдалося записати в Google Таблицю: '+e.message},502)}
}
