const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
const allowed=['manager','boss'];
export async function onRequest({request,env}) {
  const role=request.headers.get('X-Asteril-Role');
  if(!allowed.includes(role))return json({error:'Потрібен вхід.'},401);
  if(!env.TASKS_DB)return json({error:'База задач ще не підключена. Потрібна Cloudflare D1 binding TASKS_DB.'},503);
  const db=env.TASKS_DB;
  const url=new URL(request.url);
  const parts=url.pathname.split('/').filter(Boolean);
  const id=parts.length===2?Number(parts[1]):null;
  if(parts.length>2||(parts.length===2&&(!Number.isSafeInteger(id)||id<1)))return json({error:'Невірний ID задачі.'},400);
  try {
    if(request.method==='GET'&&parts.length===1){
      const {results}=await db.prepare('SELECT id,title,description,author,due_at,created_at,completed_at,completed_by FROM manager_tasks ORDER BY completed_at IS NOT NULL, due_at IS NULL, due_at ASC, created_at DESC LIMIT 1000').all();
      return json({tasks:results});
    }
    if(request.method==='POST'&&parts.length===1){
      const b=await request.json().catch(()=>({}));
      const title=String(b.title||'').trim().slice(0,160), description=String(b.description||'').trim().slice(0,2000),author=String(b.author||'').trim().slice(0,80);
      const due=b.due_at==null||b.due_at===''?null:String(b.due_at);
      if(!title||!author)return json({error:'Вкажіть назву задачі та ім’я.'},400);
      if(due&&(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(due)||!Number.isFinite(Date.parse(due))))return json({error:'Неправильний термін виконання.'},400);
      await db.prepare('INSERT INTO manager_tasks(title,description,author,due_at,created_at) VALUES(?,?,?,?,?)').bind(title,description,author,due,new Date().toISOString()).run();
      return json({ok:true},201);
    }
    if(request.method==='PATCH'&&id){
      const b=await request.json().catch(()=>({}));
      const actor=String(b.actor||'').trim().slice(0,80);
      if(!actor)return json({error:'Вкажіть ім’я.'},400);
      if(b.action==='complete'){
        const result=await db.prepare('UPDATE manager_tasks SET completed_at=?,completed_by=? WHERE id=? AND completed_at IS NULL').bind(new Date().toISOString(),actor,id).run();
        return result.meta.changes?json({ok:true}):json({error:'Задачу вже виконано або не знайдено.'},409);
      }
      if(b.action==='reopen'){
        const result=await db.prepare('UPDATE manager_tasks SET completed_at=NULL,completed_by=NULL WHERE id=? AND completed_at IS NOT NULL').bind(id).run();
        return result.meta.changes?json({ok:true}):json({error:'Задачу не знайдено.'},404);
      }
      return json({error:'Невідома дія.'},400);
    }
    return json({error:'Метод не підтримується.'},405);
  }catch(e){console.error('Tasks API error',e);return json({error:'Помилка бази задач. Перевірте, чи виконано SQL-міграцію.'},500)}
}
