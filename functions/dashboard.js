import {ensureLog} from './_dashboard-log.js';
const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
export async function onRequest({request,env,data}){
 if(data.role!=='boss')return json({error:'Доступ лише для керівника'},403);
 if(request.method!=='GET')return json({error:'Метод не підтримується'},405);
 if(!env.TASKS_DB)return json({error:'D1 TASKS_DB не підключено'},503);
 try{
  const db=env.TASKS_DB;await ensureLog(db);
  const from=new URL(request.url).searchParams.get('from'),to=new URL(request.url).searchParams.get('to');
  if(from&&!/^\d{4}-\d{2}-\d{2}$/.test(from)||to&&!/^\d{4}-\d{2}-\d{2}$/.test(to))return json({error:'Неправильна дата'},400);
  const where=(from?' AND created_at>=?':'')+(to?' AND created_at<?':'');
  const args=[...(from?[from+'T00:00:00.000Z']:[]),...(to?[new Date(Date.parse(to+'T00:00:00Z')+86400000).toISOString()]:[])];
  const events=await db.prepare('SELECT id,section,action,outcome,actor,details,created_at FROM manager_activity_log WHERE 1=1'+where+' ORDER BY id DESC LIMIT 500').bind(...args).all();
  const taskWhere=(from?' AND completed_at>=?':'')+(to?' AND completed_at<?':'');
  const taskSummary=await db.prepare('SELECT COUNT(*) AS completed FROM manager_tasks WHERE completed_at IS NOT NULL'+taskWhere).bind(...args).first();
  const tasks=await db.prepare('SELECT id,title,completed_by,completed_at FROM manager_tasks WHERE completed_at IS NOT NULL'+taskWhere+' ORDER BY completed_at DESC LIMIT 100').bind(...args).all();
  return json({ok:true,events:events.results,tasks:tasks.results,completedTasks:taskSummary.completed,historyStarts:'Історія запусків і дій записується з моменту ввімкнення журналу; попередні вигрузки недоступні.'});
 }catch(e){console.error('Dashboard error',e);return json({error:'Не вдалося завантажити статистику'},500)}
}
