export async function ensureLog(db){
 await db.prepare("CREATE TABLE IF NOT EXISTS manager_activity_log (id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL, action TEXT NOT NULL, outcome TEXT NOT NULL, actor TEXT, details TEXT, created_at TEXT NOT NULL)").run();
}
export async function record(db,section,action,outcome,actor='',details=''){
 if(!db){console.error('Dashboard event not recorded: TASKS_DB binding missing');return false}
 try{
  await ensureLog(db);
  await db.prepare('INSERT INTO manager_activity_log(section,action,outcome,actor,details,created_at) VALUES(?,?,?,?,?,?)').bind(section,action,outcome,actor,String(details).slice(0,400),new Date().toISOString()).run();
  return true;
 }catch(e){console.error('Dashboard event not recorded:',section,action,e);return false}
}

export async function recordExport(db,section,runId,count,unit,message){
 if(!db||!runId||!Number.isSafeInteger(count)||count<0)throw Error('Invalid export event');
 await ensureLog(db);
 await db.prepare("CREATE TABLE IF NOT EXISTS export_completion_ids (run_id TEXT PRIMARY KEY, section TEXT NOT NULL, recorded_at TEXT NOT NULL)").run();
 const now=new Date().toISOString();
 const inserted=await db.prepare('INSERT OR IGNORE INTO export_completion_ids(run_id,section,recorded_at) VALUES(?,?,?)').bind(runId,section,now).run();
 if(!inserted.meta.changes)return false;
 const detail=JSON.stringify({runId,count,unit,message}).slice(0,400);
 try{
  await db.prepare("INSERT INTO manager_activity_log(section,action,outcome,actor,details,created_at) VALUES(?,?,?,?,?,?)").bind(section,'Вигрузка завершена','success','Автоматично',detail,now).run();
 }catch(e){
  await db.prepare('DELETE FROM export_completion_ids WHERE run_id=?').bind(runId).run();
  throw e;
 }
 return true;
}
