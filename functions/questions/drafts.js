// Buyer-question drafts in the existing TASKS_DB Cloudflare D1 binding.
// Local browser drafts remain the offline fallback; never block Prom publishing.
const reply=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
export async function onRequest({request,env,data}){
 if(!['manager','boss'].includes(data.role))return reply({status:'error',message:'Потрібен вхід.'},401);
 if(!env.TASKS_DB)return reply({status:'error',message:'D1 TASKS_DB не підключена.'},503);
 if(!['GET','PUT','DELETE'].includes(request.method))return reply({status:'error',message:'Метод не підтримується.'},405);
 try{
  const db=env.TASKS_DB;
  await db.prepare('CREATE TABLE IF NOT EXISTS buyer_question_drafts (draft_key TEXT PRIMARY KEY, draft_text TEXT NOT NULL, updated_at TEXT NOT NULL)').run();
  if(request.method==='GET'){
   const {results}=await db.prepare('SELECT draft_key,draft_text,updated_at FROM buyer_question_drafts LIMIT 5000').all();
   return reply({status:'ok',items:Object.fromEntries(results.map(r=>[r.draft_key,{text:r.draft_text,updated_at:r.updated_at}]))});
  }
  const body=await request.json().catch(()=>({}));
  const key=String(body.key||'').trim();
  if(!/^\\d+:\\d+$/.test(key)||key.length>100)return reply({status:'error',message:'Неправильний ключ запитання.'},400);
  if(request.method==='DELETE'){
   await db.prepare('DELETE FROM buyer_question_drafts WHERE draft_key=?').bind(key).run();
   return reply({status:'ok'});
  }
  const value=String(body.text??'');
  if(value.length>10000)return reply({status:'error',message:'Занадто довга чернетка.'},400);
  await db.prepare('INSERT INTO buyer_question_drafts(draft_key,draft_text,updated_at) VALUES(?,?,?) ON CONFLICT(draft_key) DO UPDATE SET draft_text=excluded.draft_text,updated_at=excluded.updated_at').bind(key,value,new Date().toISOString()).run();
  return reply({status:'ok'});
 }catch(e){console.error('Buyer drafts D1 error',e);return reply({status:'error',message:'Не вдалося звернутися до D1. Чернетки залишаються в браузері.'},503)}
}
