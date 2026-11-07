import {record} from './_dashboard-log.js';
const reply=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
export async function onRequest({request,env,data}){
 if(!['manager','boss'].includes(data.role))return reply({error:'Потрібен вхід'},401);
 if(!env.TTN_SCRIPT_URL||!env.TTN_API_SECRET)return reply({error:'Інтеграція ТТН очікує налаштування Google Apps Script'},503);
 const url=new URL(request.url),action=url.searchParams.get('action');
 if(!['list','process'].includes(action))return reply({error:'Невідома дія'},400);
 if(action==='list'&&request.method!=='GET'||action==='process'&&request.method!=='POST')return reply({error:'Метод не підтримується'},405);
 let payload={action,secret:env.TTN_API_SECRET};
 if(action==='process'){
  const body=await request.json().catch(()=>null);
  if(!body||!Number.isInteger(body.row)||body.row<2||!['send','bogdan','return','impossible'].includes(body.operation)||!['Яна','Наталя'].includes(body.manager))return reply({error:'Некоректні дані'},400);
  payload={...payload,row:body.row,operation:body.operation,manager:body.manager,detail:String(body.detail||'').slice(0,1000)};
  if(body.operation==='impossible'&&!payload.detail.trim())return reply({error:'Вкажіть причину неможливості виконання'},400);
 }
 try{
  const response=await fetch(env.TTN_SCRIPT_URL,{method:'POST',headers:{'Content-Type':'text/plain;charset=utf-8'},body:JSON.stringify(payload),redirect:'follow'});
  if(!response.ok)return reply({error:'Сервіс Google недоступний'},502);
  const result=await response.json();
  if(action==='process'&&result.ok===true)await record(env.TASKS_DB,'Зміни з ТТН',payload.operation,'success',payload.manager,'Рядок таблиці '+payload.row);
  return reply(result,result.ok===false?409:200);
 }catch{return reply({error:'Не вдалося отримати відповідь Google Apps Script. Перевірте стан запиту в таблиці перед повторною відправкою.'},502)}
}