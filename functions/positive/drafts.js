// Positive review answer drafts. Uses the existing Cloudflare Pages D1 binding TASKS_DB.
const json=(body,status=200)=>Response.json(body,{status,headers:{'Cache-Control':'no-store'}});
export async function onRequest({request,env,data}){
 if(!['manager','boss'].includes(data.role))return json({status:'error',message:'Потрібен вхід.'},401);
 if(!env.TASKS_DB)return json({status:'error',message:'D1 TASKS_DB не підключена.'},503);
 if(!['GET','PUT','DELETE'].includes(request.method))return json({status:'error',message:'Метод не підтримується.'},405);
 try{
  const db=env.TASKS_DB;
  await db.prepare('CREATE TABLE IF NOT EXISTS positive_reply_drafts (draft_key TEXT PRIMARY KEY, review_day TEXT NOT NULL, draft_text TEXT NOT NULL, updated_at TEXT NOT NULL)').run();
  if(request.method==='GET'){
   const day=new URL(request.url).searchParams.get('day')||'';
   if(!/^\\d{4}-\\d{2}-\\d{2}$/.test(day))return json({status:'error',message:'Невірна дата.'},400);
   const {results}=await db.prepare('SELECT draft_key,draft_text,updated_at FROM positive_reply_drafts WHERE review_day=? LIMIT 5000').bind(day).all();
   return json({status:'ok',items:Object.fromEntries(results.map(r=>[r.draft_key,{text:r.draft_text,updated_at:r.updated_at}]))});
  }
  const body=await request.json().catch(()=>({}));
  const key=String(body.key||'').trim(),day=String(body.day||'');
  if(!/^\\d+:\\d+$/.test(key)||key.length>100||!/^\\d{4}-\\d{2}-\\d{2}$/.test(day))return json({status:'error',message:'Неправильний ключ або дата.'},400);
  if(request.method==='DELETE'){
   await db.prepare('DELETE FROM positive_reply_drafts WHERE draft_key=? AND review_day=?').bind(key,day).run();
   return json({status:'ok'});
  }
  const value=String(body.text??'');
  if(value.length>10000)return json({status:'error',message:'Занадто довга чернетка.'},400);
  await db.prepare('INSERT INTO positive_reply_drafts(draft_key,review_day,draft_text,updated_at) VALUES(?,?,?,?) ON CONFLICT(draft_key) DO UPDATE SET review_day=excluded.review_day,draft_text=excluded.draft_text,updated_at=excluded.updated_at').bind(key,day,value,new Date().toISOString()).run();
  return json({status:'ok'});
 }catch(e){console.error('Positive drafts D1 error',e);return json({status:'error',message:'D1 тимчасово недоступна. Чернетки залишаються в браузері.'},503)}
}
