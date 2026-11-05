const json=(x,s=200)=>Response.json(x,{status:s,headers:{'Cache-Control':'no-store'}});
const str=(x,n=500)=>String(x??'').trim().slice(0,n);
export async function onRequest({request,env,data}){
 if(!['manager','boss'].includes(data.role))return json({error:'Потрібен вхід'},401);
 if(!env.TASKS_DB)return json({error:'D1 не підключена'},503);
 const db=env.TASKS_DB,u=new URL(request.url),action=u.pathname.split('/')[2];
 try{
  if(request.method==='GET'&&action==='search'){
   const q=str(u.searchParams.get('q'),100),page=Math.max(1,Math.min(10000,Number(u.searchParams.get('page'))||1));
   const where=q?' WHERE title LIKE ? OR sku LIKE ? OR product_id LIKE ?':'',args=q?Array(3).fill('%'+q+'%'):[];
   const total=(await db.prepare('SELECT COUNT(*) n FROM product_catalog'+where).bind(...args).first()).n;
   const {results}=await db.prepare('SELECT product_id,sku,title,category,brand FROM product_catalog'+where+' ORDER BY title LIMIT 30 OFFSET ?').bind(...args,(page-1)*30).all();
   return json({items:results,total,page,pages:Math.ceil(total/30)});
  }
  if(request.method==='GET'&&action==='item'){
   const id=str(u.searchParams.get('id'),150),item=await db.prepare('SELECT * FROM product_catalog WHERE product_id=?').bind(id).first();
   if(!item)return json({error:'Товар не знайдено'},404);
   const k=await db.prepare('SELECT * FROM product_knowledge WHERE product_id=?').bind(id).first();
   return json({item,knowledge:k?{faq:JSON.parse(k.faq_json),instructions:k.instructions,related:JSON.parse(k.related_json)}:{faq:[],instructions:'',related:[]}});
  }
  if(data.role==='boss'&&action==='review'){
   if(request.method==='GET'){
    const status=str(u.searchParams.get('status')||'pending',20);
    if(!['pending','approved','rejected'].includes(status))return json({error:'Невірний статус'},400);
    const {results}=await db.prepare('SELECT r.*,p.title product_title FROM product_faq_review r LEFT JOIN product_catalog p ON p.product_id=r.product_id WHERE r.status=? ORDER BY r.created_at,r.id LIMIT 200').bind(status).all();
    const totals=await db.prepare('SELECT status,COUNT(*) n FROM product_faq_review GROUP BY status').all();
    return json({items:results,totals:totals.results});
   }
   if(request.method==='POST'){
    const b=await request.json();
    if(!Array.isArray(b.items)||b.items.length>50)return json({error:'Максимум 50 записів'},400);
    const statements=b.items.filter(x=>x.sku&&x.question&&x.answer&&x.source_answer_id).map(x=>db.prepare('INSERT OR IGNORE INTO product_faq_review(id,sku,product_id,question,answer,original_question,original_answer,source_question_id,source_answer_id,source_date) VALUES(?,?,(SELECT product_id FROM product_catalog WHERE sku=? LIMIT 1),?,?,?,?,?,?,?)').bind(str(x.source_answer_id,100),str(x.sku,150),str(x.sku,150),str(x.question,500),str(x.answer,5000),str(x.original_question,5000),str(x.original_answer,5000),str(x.source_question_id,100),str(x.source_answer_id,100),str(x.source_date,100)));
    if(statements.length)await db.batch(statements);
    return json({ok:true,processed:statements.length});
   }
   if(request.method==='PUT'){
    const b=await request.json(),id=str(b.id,100),decision=str(b.decision,20);
    if(!['approve','reject'].includes(decision))return json({error:'Невірна дія'},400);
    const record=await db.prepare('SELECT * FROM product_faq_review WHERE id=?').bind(id).first();
    if(!record||record.status!=='pending')return json({error:'Запис уже оброблено або не знайдено'},409);
    if(decision==='reject'){await db.prepare("UPDATE product_faq_review SET status='rejected',reviewed_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'").bind(id).run();return json({ok:true})}
    const q=str(b.question,500),a=str(b.answer,5000),pid=str(b.product_id||record.product_id,150);
    if(!q||!a||!pid)return json({error:'Потрібно заповнити питання, відповідь та обрати товар'},400);
    const product=await db.prepare('SELECT product_id FROM product_catalog WHERE product_id=?').bind(pid).first();
    if(!product)return json({error:'Товар не знайдено в каталозі'},400);
    const existing=await db.prepare('SELECT * FROM product_knowledge WHERE product_id=?').bind(pid).first();
    const faq=existing?JSON.parse(existing.faq_json):[];
    if(faq.length>=50)return json({error:'Для товару вже є 50 FAQ'},400);
    if(!faq.some(x=>x.q.trim().toLowerCase()===q.toLowerCase()))faq.push({q,a});
    await db.batch([
      db.prepare('INSERT INTO product_knowledge(product_id,faq_json,instructions,related_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET faq_json=excluded.faq_json,updated_at=excluded.updated_at').bind(pid,JSON.stringify(faq),existing?.instructions||'',existing?.related_json||'[]',new Date().toISOString()),
      db.prepare("UPDATE product_faq_review SET status='approved',product_id=?,question=?,answer=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'").bind(pid,q,a,id)
    ]);
    return json({ok:true});
   }
  }
  if(data.role!=='boss')return json({error:'Лише для Крутого боса'},403);
  if(request.method==='POST'&&action==='import'){
   const b=await request.json();if(!Array.isArray(b.items)||!b.items.length||b.items.length>60)return json({error:'Максимум 60 товарів у пакеті'},400);
   const statements=b.items.map(x=>db.prepare('INSERT INTO product_catalog(product_id,sku,title,category,brand,description,image_url,product_url,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET sku=excluded.sku,title=excluded.title,category=excluded.category,brand=excluded.brand,description=excluded.description,image_url=excluded.image_url,product_url=excluded.product_url,updated_at=excluded.updated_at').bind(str(x.product_id,150),str(x.sku,150),str(x.title,600),str(x.category,250),str(x.brand,250),str(x.description,15000),str(x.image_url,1500),str(x.product_url,1500),new Date().toISOString()));
   await db.batch(statements);return json({ok:true,count:statements.length});
  }
  if(request.method==='PUT'&&action==='knowledge'){
   const b=await request.json(),id=str(b.product_id,150);
   const exists=await db.prepare('SELECT product_id FROM product_catalog WHERE product_id=?').bind(id).first();
   if(!exists)return json({error:'Товар не знайдено'},404);
   const faq=Array.isArray(b.faq)?b.faq.slice(0,50).map(x=>({q:str(x.q,500),a:str(x.a,5000)})):[];
   const related=Array.isArray(b.related)?b.related.slice(0,50).map(x=>str(x,150)):[];
   await db.prepare('INSERT INTO product_knowledge(product_id,faq_json,instructions,related_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET faq_json=excluded.faq_json,instructions=excluded.instructions,related_json=excluded.related_json,updated_at=excluded.updated_at').bind(id,JSON.stringify(faq),str(b.instructions,30000),JSON.stringify(related),new Date().toISOString()).run();
   return json({ok:true});
  }
  return json({error:'Невідомий запит'},404);
 }catch(e){console.error(e);return json({error:'Помилка каталогу. Перевірте міграцію 0004.'},500)}
}