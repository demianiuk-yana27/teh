const json=(x,s=200)=>Response.json(x,{status:s,headers:{'Cache-Control':'no-store'}});
const str=(x,n=500)=>String(x??'').trim().slice(0,n);
const relatedRules=[
 {re:/вакууматор|вакуумн.*пакувальник|вакуумн.*упаковщик/i,terms:['пакети для вакуумування','рулон для вакуумування'],needsReview:true},
 {re:/столик.*ноутбук|стіл.*ноутбук|підставк.*ноутбук/i,terms:['органайзер для кабелів','килимок для миші','лампа настільна']},
 {re:/шуруповерт|дрил|дрель|перфоратор/i,terms:['біти','свердла','набір інструментів']},
 {re:/камера відеоспостереж|ip камера|відеокамер/i,terms:['карта пам','micro sd','блок живлення'],needsReview:true},
 {re:/намет|палатк/i,terms:['спальний мішок','каремат','туристичний ліхтар']},
 {re:/телефон|смартфон/i,terms:['чохол','захисне скло','кабель usb'],needsReview:true},
 {re:/ноутбук/i,terms:['миша','сумка для ноутбука','підставка для ноутбука']},
 {re:/пилосос/i,terms:['фільтр для пилососа','насадка для пилососа'],needsReview:true},
 {re:/рація|радіостанц/i,terms:['гарнітура для рації','акумулятор для рації'],needsReview:true},
 {re:/кавоварка|кавомашин/i,terms:['кавомолка','кава']},
 {re:/принтер/i,terms:['папір для принтера','картридж'],needsReview:true}
];
const relatedRule=title=>relatedRules.find(x=>x.re.test(title));
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
  if(request.method==='GET'&&action==='suggest-related'){
   const id=str(u.searchParams.get('id'),150);
   const item=await db.prepare('SELECT product_id,sku,title,category,brand FROM product_catalog WHERE product_id=?').bind(id).first();
   if(!item)return json({error:'Товар не знайдено'},404);
   const rule=relatedRule(item.title);
   if(!rule)return json({item,items:[],reason:'Для цієї групи товарів ще немає правила підбору.'});
   const found=[];
   for(const term of rule.terms){
    const {results}=await db.prepare('SELECT product_id,sku,title,category FROM product_catalog WHERE product_id<>? AND title LIKE ? ORDER BY title LIMIT 5').bind(id,'%'+term+'%').all();
    const x=results.find(y=>!found.some(z=>z.product_id===y.product_id));if(x)found.push({...x,match_reason:term});
   }
   return json({item,items:found.slice(0,18),reason:rule.needsReview?'Кандидати за типами аксесуарів. Перевірте сумісність із конкретною моделлю перед збереженням.':'По одному кандидату кожного типу. Перевірте доречність перед збереженням.'});
  }
  if(action==='related-bulk'&&data.role==='boss'){
   const cursor=str(u.searchParams.get('after'),150);
   const rows=(await db.prepare('SELECT product_id,sku,title FROM product_catalog WHERE product_id>? ORDER BY product_id LIMIT 20').bind(cursor).all()).results;
   const proposals=[];
   for(const p of rows){
    const rule=relatedRule(p.title);if(!rule)continue;
    const known=await db.prepare('SELECT related_json FROM product_knowledge WHERE product_id=?').bind(p.product_id).first();
    if(known&&JSON.parse(known.related_json||'[]').length)continue;
    const related=[];
    for(const term of rule.terms){
     const candidates=(await db.prepare('SELECT product_id,sku,title FROM product_catalog WHERE product_id<>? AND title LIKE ? ORDER BY title LIMIT 5').bind(p.product_id,'%'+term+'%').all()).results;
     const candidate=candidates.find(x=>!related.some(y=>y.product_id===x.product_id));
     if(candidate)related.push({...candidate,match_reason:term});
    }
    if(related.length)proposals.push({product:p,related,needsReview:!!rule.needsReview});
   }
   const next=rows.length?rows[rows.length-1].product_id:cursor;
   if(request.method==='GET')return json({proposals,next,done:rows.length<20,scanned:rows.length});
   if(request.method==='POST'){
    const b=await request.json();
    if(!Array.isArray(b.approved)||b.approved.length>20)return json({error:'Некоректний пакет'},400);
    const approved=new Set(b.approved.map(x=>str(x,150)));
    const statements=proposals.filter(x=>approved.has(x.product.product_id)).map(x=>db.prepare("INSERT INTO product_knowledge(product_id,faq_json,instructions,related_json,updated_at) VALUES(?,'[]','',?,CURRENT_TIMESTAMP) ON CONFLICT(product_id) DO UPDATE SET related_json=excluded.related_json,updated_at=excluded.updated_at WHERE related_json IS NULL OR related_json='[]'").bind(x.product.product_id,JSON.stringify(x.related.map(y=>y.product_id))));
    if(statements.length)await db.batch(statements);
    return json({ok:true,processed:statements.length,next,done:rows.length<20,scanned:rows.length});
   }
   return json({error:'Метод не підтримується'},405);
  }
  if(data.role==='boss'&&action==='review'){
   if(request.method==='POST'&&u.searchParams.get('operation')==='classify'){
    const b=await request.json();
    if(!Array.isArray(b.ids)||b.ids.length>200)return json({error:'Максимум 200 FAQ за раз'},400);
    const results=[];
    for(const id of b.ids){
     const record=await db.prepare('SELECT id,sku,product_id,question,answer,original_question,original_answer FROM product_faq_review WHERE id=? AND status=?').bind(str(id,100),'pending').first();
     if(!record)continue;
     const matches=(await db.prepare('SELECT product_id,title FROM product_catalog WHERE sku=? OR product_id=? LIMIT 20').bind(record.sku,record.sku).all()).results;
     const product_id=record.product_id||(matches.length===1?matches[0].product_id:null);
     const answer=str(record.answer,5000),question=str(record.question,500);
     const a=answer.toLocaleLowerCase('uk').replace(/[.!?\\s]+$/g,'').trim();
     const q=question.toLocaleLowerCase('uk');
     const ambiguous=/як в попередн|так(?:а|і|ий|е)? ж як|так(?:а|і|ий|е)? сам(?:а|і|ий|е)?|як раніше|дивіться вище|на фото|скину фото|не знаю|напевно|мабуть|можливо|не вказ|немає інформац|нема інформац|не перевір|потрібно уточн|залежить|не гарант|певно|орієнтовно/i.test(a);
     const offTopic=/користуйтесь\\s+(?:цим\\s+)?чатом|користуйтеся\\s+(?:цим\\s+)?чатом|пишіть\\s+(?:у|в)\\s+(?:цей|цьому)\\s+чат|не\\s+(?:в\\s+той|сюди)\\s+чат|помилково\\s+(?:написал|відправил)/i.test(a);
     const temporary=/сьогодні|завтра|ціна|вартіст|залишил|наявност|парті|пересорт|відправлю|уточню|пізніше/i.test(a+' '+q);
     const shortConcrete=/^(?:тут\\s+)?(?:один|одна|одне|два|дві|три|чотири|п'ять|загальн(?:ий|а|е)|фарба|фарбован(?:е|і|а)|пластик|пластиков(?:ий|а|е)|алюміній|алюмінієв(?:ий|а|е)|метал|металев(?:ий|а|е)|блакитн(?:ий|а|е|і)|чорн(?:ий|а|е|і)|біл(?:ий|а|е|і)|micro[ -]?usb|usb[ -]?c|type[ -]?c|lightning|до\\s*\\d+\\s*(?:гб|gb)|\\d+[xх×*]\\d+)/i.test(a);
     const yesNo=/^(так|ні|да|нет|є|немає|не має|входить|не входить|у комплекті|в комплекті)$/.test(a);
     const clearBinary=/^(чи |є |має |наявн|входить|підтримує|можна |працює|сумісн|йде |іде )/.test(q)&&!/(який|яка|яке|які|скільки|коли|де|чому|або|\\sта\\s)/.test(q)&&(q.match(/\\?/g)||[]).length<=1;
     const meaningful=shortConcrete||/\\d/.test(a)||a.length>=18||(yesNo&&clearBinary);
     const cleanedQuestion=question.replace(/^(?:добр(?:ого|ий)\\s+(?:дня|ранку)|привіт|підкажіть(?:\\s+будь ласка)?)[!,.:\\s-]*/i,'').replace(/(?:^|\\s)\\d{9,14}(?=\\s|$)/g,' ').replace(/\\s+/g,' ').trim();
     let status='ready',reason='Змістовна відповідь; перевірте перед публікацією',category='content';
     if(!product_id||matches.length>1){status='review';category='product_match';reason=!product_id?'Товар не зіставлено':'Кілька карток за артикулом — перевірте правильну модель';}
     else if(offTopic||ambiguous||temporary||!a){status='review';category=offTopic?'off_topic':ambiguous?'missing_context':temporary?'temporary':'empty';reason=offTopic?'Службове повідомлення, не відповідь про товар':ambiguous?'Відповідь залежить від відсутнього контексту':temporary?'Тимчасова інформація, не для постійного FAQ':'Порожня відповідь';}
     else if(!meaningful){reason='Коротка відповідь — перевірте зміст перед публікацією';category='short_answer';}
     else if(shortConcrete){reason='Коротка, але конкретна характеристика';category='short_concrete';}
     else if(yesNo&&clearBinary){reason='Однозначна відповідь на конкретне запитання';category='binary';}
     if(/постійн.*запис|запис.*постійн|\\bвисот[аи]\\b|\\bрозмір[и]?\\b/.test(q)&&/^(постійно|\\d+(?:[.,]\\d+)?[xх×*]\\d+)/.test(a)){status='review';category='specification';reason='Уточніть умови роботи або порядок розмірів';}
     results.push({id:record.id,status,product_id,reason,category,suggested_question:cleanedQuestion!==question?cleanedQuestion:null});
    }
    return json({items:results});
   }
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
    if(faq.some(x=>x.q.trim().toLowerCase()===q.toLowerCase()))return json({error:'Таке питання вже є у FAQ товару. Перевірте дубль вручну.'},409);
    faq.push({q,a});
    await db.batch([
      db.prepare('INSERT INTO product_knowledge(product_id,faq_json,instructions,related_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET faq_json=excluded.faq_json,updated_at=excluded.updated_at').bind(pid,JSON.stringify(faq),existing?.instructions||'',existing?.related_json||'[]',new Date().toISOString()),
      db.prepare("UPDATE product_faq_review SET status='approved',product_id=?,question=?,answer=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=? AND status='pending'").bind(pid,q,a,id)
    ]);
    return json({ok:true});
   }
  }
  if(data.role!=='boss')return json({error:'Лише для Крутого боса'},403);
  if(request.method==='POST'&&action==='cleanup-chat-faq'){
   const bad=a=>{
    const normalized=String(a||'').toLocaleLowerCase('uk').replace(/[.!?,;:«»"'’()\s]+/g,' ').trim();
    return /^(?:користуйтесь|користуйтеся) (?:цим )?чатом$|^не (?:той|цей) чат$/.test(normalized);
   };
   let cursor='',removed=0,scanned=0,matched=0;
   // Scan published FAQ JSON directly, not only review records.
   for(let page=0;page<200;page++){
    const {results:rows}=await db.prepare("SELECT product_id,faq_json FROM product_knowledge WHERE product_id>? AND LOWER(faq_json) LIKE '%чат%' ORDER BY product_id LIMIT 250").bind(cursor).all();
    if(!rows.length)break;
    for(const row of rows){
     scanned++;cursor=row.product_id;
     let faq;
     try{faq=JSON.parse(row.faq_json||'[]')}catch(e){continue}
     if(!Array.isArray(faq))continue;
     const next=faq.filter(item=>!bad(item.a));
     const count=faq.length-next.length;
     if(!count)continue;
     matched++;
     await db.prepare('UPDATE product_knowledge SET faq_json=?,updated_at=? WHERE product_id=?').bind(JSON.stringify(next),new Date().toISOString(),row.product_id).run();
     removed+=count;
    }
    if(rows.length<250)break;
   }
   const {results:reviewRows}=await db.prepare("SELECT id,answer FROM product_faq_review WHERE status='approved' AND LOWER(answer) LIKE '%чат%' LIMIT 500").all();
   let marked=0;
   for(const row of reviewRows)if(bad(row.answer)){
    await db.prepare("UPDATE product_faq_review SET status='rejected',reviewed_at=CURRENT_TIMESTAMP WHERE id=? AND status='approved'").bind(row.id).run();
    marked++;
   }
   return json({ok:true,removed,matched,scanned,marked});
  }
  if(request.method==='POST'&&action==='deduplicate-skus'){
   const {results:groups}=await db.prepare("SELECT sku,COUNT(*) n FROM product_catalog WHERE sku IS NOT NULL AND TRIM(sku)<>'' GROUP BY sku HAVING COUNT(*)>1 ORDER BY sku LIMIT 15").all();
   let removed=0,merged=0;
   for(const group of groups){
    const {results:products}=await db.prepare("SELECT p.product_id,p.title,k.faq_json,k.instructions,k.related_json FROM product_catalog p LEFT JOIN product_knowledge k ON k.product_id=p.product_id WHERE p.sku=? ORDER BY (CASE WHEN k.product_id IS NOT NULL THEN 1 ELSE 0 END) DESC,p.product_id").bind(group.sku).all();
    if(products.length<2)continue;
    const keep=products[0],extras=products.slice(1),keepId=keep.product_id;
    let faq=JSON.parse(keep.faq_json||'[]'),instructions=keep.instructions||'',related=JSON.parse(keep.related_json||'[]');
    for(const p of extras){
     for(const item of JSON.parse(p.faq_json||'[]'))if(item.q&&!faq.some(x=>String(x.q).trim().toLowerCase()===String(item.q).trim().toLowerCase())&&faq.length<50)faq.push(item);
     if(!instructions&&p.instructions)instructions=p.instructions;
     for(const id of JSON.parse(p.related_json||'[]'))if(id!==keepId&&!related.includes(id)&&related.length<50)related.push(id);
    }
    const statements=[db.prepare("INSERT INTO product_knowledge(product_id,faq_json,instructions,related_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET faq_json=excluded.faq_json,instructions=excluded.instructions,related_json=excluded.related_json,updated_at=excluded.updated_at").bind(keepId,JSON.stringify(faq),instructions,JSON.stringify(related),new Date().toISOString())];
    for(const p of extras){
     statements.push(db.prepare("UPDATE product_faq_review SET product_id=? WHERE product_id=?").bind(keepId,p.product_id));
     statements.push(db.prepare("DELETE FROM product_knowledge WHERE product_id=?").bind(p.product_id));
     statements.push(db.prepare("DELETE FROM product_catalog WHERE product_id=?").bind(p.product_id));
    }
    await db.batch(statements);
    removed+=extras.length;merged++;
   }
   return json({ok:true,removed,groups:merged,done:groups.length<15});
  }
  if(request.method==='GET'&&action==='duplicate-audit'){
   const page=Math.max(1,Math.min(10000,Number(u.searchParams.get('page'))||1));
   const limit=30,offset=(page-1)*limit;
   const totals=await db.prepare("SELECT COUNT(*) groups_count,COALESCE(SUM(n-1),0) extra_rows FROM (SELECT sku,COUNT(*) n FROM product_catalog WHERE sku IS NOT NULL AND TRIM(sku)<>'' GROUP BY sku HAVING COUNT(*)>1)").first();
   const {results:groups}=await db.prepare("SELECT sku,COUNT(*) n FROM product_catalog WHERE sku IS NOT NULL AND TRIM(sku)<>'' GROUP BY sku HAVING COUNT(*)>1 ORDER BY n DESC,sku LIMIT ? OFFSET ?").bind(limit,offset).all();
   const items=[];
   for(const group of groups){
    const {results:products}=await db.prepare("SELECT p.product_id,p.sku,p.title,p.category,CASE WHEN k.product_id IS NULL THEN 0 ELSE 1 END has_knowledge,COALESCE(json_array_length(k.faq_json),0) faq_count,COALESCE(json_array_length(k.related_json),0) related_count,CASE WHEN LENGTH(TRIM(COALESCE(k.instructions,'')))>0 THEN 1 ELSE 0 END has_instructions,(SELECT COUNT(*) FROM product_faq_review r WHERE r.product_id=p.product_id) review_count FROM product_catalog p LEFT JOIN product_knowledge k ON k.product_id=p.product_id WHERE p.sku=? ORDER BY p.product_id LIMIT 30").bind(group.sku).all();
    items.push({sku:group.sku,count:group.n,products,has_variants:new Set(products.map(p=>p.title.trim().toLocaleLowerCase('uk'))).size>1});
   }
   return json({totals,page,pages:Math.ceil(totals.groups_count/limit),items,read_only:true});
  }
  if(request.method==='POST'&&action==='import'){
   const b=await request.json();if(!Array.isArray(b.items)||!b.items.length||b.items.length>60)return json({error:'Максимум 60 товарів у пакеті'},400);
   const statements=b.items.map(x=>db.prepare('INSERT INTO product_catalog(product_id,sku,title,category,brand,description,image_url,product_url,updated_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET sku=excluded.sku,title=excluded.title,category=excluded.category,brand=excluded.brand,description=excluded.description,image_url=excluded.image_url,product_url=excluded.product_url,updated_at=excluded.updated_at').bind(str(x.product_id,150),str(x.sku,150),str(x.title,600),str(x.category,250),str(x.brand,250),str(x.description,15000),str(x.image_url,1500),str(x.product_url,1500),new Date().toISOString()));
   await db.batch(statements);return json({ok:true,count:statements.length});
  }
  if(request.method==='PUT'&&action==='related'){
   const b=await request.json(),id=str(b.product_id,150);
   if(!Array.isArray(b.related)||b.related.length>50)return json({error:'Максимум 50 супутніх товарів'},400);
   const related=[...new Set(b.related.map(x=>str(x,150)).filter(Boolean))].filter(x=>x!==id);
   const exists=await db.prepare('SELECT product_id FROM product_catalog WHERE product_id=?').bind(id).first();
   if(!exists)return json({error:'Товар не знайдено'},404);
   for(const rid of related){if(!await db.prepare('SELECT product_id FROM product_catalog WHERE product_id=?').bind(rid).first())return json({error:'Невідомий ID супутнього товару: '+rid},400)}
   const existing=await db.prepare('SELECT * FROM product_knowledge WHERE product_id=?').bind(id).first();
   const merged=[...new Set([...(existing?JSON.parse(existing.related_json):[]),...related])].slice(0,50);
   await db.prepare('INSERT INTO product_knowledge(product_id,faq_json,instructions,related_json,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET related_json=excluded.related_json,updated_at=excluded.updated_at').bind(id,existing?.faq_json||'[]',existing?.instructions||'',JSON.stringify(merged),new Date().toISOString()).run();
   return json({ok:true,count:merged.length});
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
 }catch(e){console.error('products/'+action,e);return json({error:action==='review'&&data.role==='boss'?'Помилка FAQ: '+str(e.message,350):'Помилка каталогу. Перевірте міграцію 0004.'},500)}
}