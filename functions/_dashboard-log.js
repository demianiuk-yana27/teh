export async function ensureLog(db){
 await db.prepare("CREATE TABLE IF NOT EXISTS manager_activity_log (id INTEGER PRIMARY KEY AUTOINCREMENT, section TEXT NOT NULL, action TEXT NOT NULL, outcome TEXT NOT NULL, actor TEXT, details TEXT, created_at TEXT NOT NULL)").run();
}
export async function record(db,section,action,outcome,actor='',details=''){
 if(!db)return;
 try{await ensureLog(db);await db.prepare('INSERT INTO manager_activity_log(section,action,outcome,actor,details,created_at) VALUES(?,?,?,?,?,?)').bind(section,action,outcome,actor,String(details).slice(0,400),new Date().toISOString()).run()}catch(e){console.error('Dashboard logging failed',e)}
}
