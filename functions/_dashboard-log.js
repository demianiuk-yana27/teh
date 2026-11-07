export async function ensureLog(db){
 await db.prepare("CREATE TABLE IF NOT EXISTS manager_activity_log (id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL, action TEXT NOT NULL, outcome TEXT NOT NULL, actor TEXT, details TEXT, created_at TEXT NOT NULL)").run();
}
export async function record(db,section,action,outcome,actor='',details=''){
 if(!db)return;
 try{await ensureLog(db);await db.prepare('INSERT INTO manager_activity_log(section,action,outcome,actor,details,created_at) VALUES(?,?,?,?,?,?)').bind(section,action,outcome,actor,String(details).slice(0,400),new Date().toISOString()).run()}catch(e){console.error('Dashboard logging failed',e)}
}

export async function recordExport(db,section,runId,count,unit,message){
 if(!db||!runId||!Number.isSafeInteger(count)||count<0)return;
 try{
  await ensureLog(db);
  await db.prepare("CREATE UNIQUE INDEX IF NOT EXISTS manager_export_run_unique ON manager_activity_log(details) WHERE action='Вигрузка завершена'").run();
  const detail=JSON.stringify({runId,count,unit,message}).slice(0,400);
  await db.prepare("INSERT OR IGNORE INTO manager_activity_log(section,action,outcome,actor,details,created_at) VALUES(?,?,?,?,?,?)").bind(section,'Вигрузка завершена','success','Автоматично',detail,new Date().toISOString()).run();
 }catch(e){console.error('Export completion logging failed',e)}
}
