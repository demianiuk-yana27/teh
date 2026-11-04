const reply=(x,status=200)=>Response.json(x,{status,headers:{'Cache-Control':'no-store'}});
const validTypes=new Set(['text','image','video','embed','list']);
const validId=x=>/^\d+$/.test(String(x||''))&&Number(x)>0;
const cleanBlocks=blocks=>{
 if(!Array.isArray(blocks)||blocks.length>80)throw Error('Дозволено до 80 блоків.');
 return blocks.map(b=>{
  const type=String(b.type||'');
  if(!validTypes.has(type))throw Error('Невідомий тип блоку.');
  const text=String(b.text||'').slice(0,12000);
  const media=String(b.media||'');
  if(['image','video'].includes(type)&&!/^materials\/[a-f0-9-]{36}\.(?:jpg|jpeg|png|webp|gif|mp4|webm|mov)$/i.test(media))throw Error('Спочатку завантажте файл.');
  if(type==='embed'){
   let u;try{u=new URL(String(b.url||''))}catch{throw Error('Неправильне посилання на відео.')}
   if(u.protocol!=='https:'||!(['www.youtube.com','youtube.com','youtu.be','www.youtube-nocookie.com','vimeo.com','player.vimeo.com'].includes(u.hostname)))throw Error('Підтримуються посилання YouTube та Vimeo.');
   return {type,url:u.toString(),text};
  }
  return {type,text,media: ['image','video'].includes(type)?media:''};
 });
};
export async function onRequest({request,env,data}){
 if(!['boss','manager'].includes(data.role))return reply({error:'Потрібен вхід.'},401);
 if(!env.TASKS_DB)return reply({error:'Підключіть D1 binding TASKS_DB.'},503);
 const db=env.TASKS_DB,url=new URL(request.url),parts=url.pathname.split('/').filter(Boolean);
 const id=parts[1],media=parts[1]==='media',method=request.method;
 try{
  if(media){
   if(parts.length!==3||!/^([a-f0-9-]{36})\.(jpg|jpeg|png|webp|gif|mp4|webm|mov)$/i.test(parts[2]))return reply({error:'Невірний файл.'},400);
   if(!env.TRAINING_MEDIA)return reply({error:'Підключіть R2 binding TRAINING_MEDIA.'},503);
   const key='materials/'+parts[2];
   if(method==='GET'){
    const obj=await env.TRAINING_MEDIA.get(key);if(!obj)return reply({error:'Файл не знайдено.'},404);
    return new Response(obj.body,{headers:{'Content-Type':obj.httpMetadata?.contentType||'application/octet-stream','Cache-Control':'private, max-age=3600','X-Content-Type-Options':'nosniff','Content-Disposition':'inline'}});
   }
   if(data.role!=='boss')return reply({error:'Лише для ролі «Крутий бос».'},403);
   if(method==='PUT'){
    const type=request.headers.get('Content-Type')||'';
    const allowed={'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','webp':'image/webp','gif':'image/gif','mp4':'video/mp4','webm':'video/webm','mov':'video/quicktime'};
    const ext=parts[2].split('.').pop().toLowerCase();
    if(type.split(';')[0]!==allowed[ext])return reply({error:'Невідповідний тип файлу.'},400);
    const length=Number(request.headers.get('Content-Length')||0);
    if(!length||length>50*1024*1024)return reply({error:'Максимальний розмір файлу — 50 МБ.'},413);
    const body=await request.arrayBuffer();
    if(body.byteLength!==length)return reply({error:'Помилка завантаження файлу.'},400);
    await env.TRAINING_MEDIA.put(key,body,{httpMetadata:{contentType:allowed[ext]}});
    return reply({key,url:'/materials/media/'+parts[2]},201);
   }
   return reply({error:'Метод не підтримується.'},405);
  }
  if(parts.length===1&&method==='GET'){
   const {results}=await db.prepare('SELECT id,title,summary,status,created_at,updated_at FROM training_materials WHERE status=? OR ?=? ORDER BY updated_at DESC LIMIT 500').bind('published',data.role,'boss').all();
   return reply({materials:results});
  }
  if(parts.length===2&&validId(id)&&method==='GET'){
   const row=await db.prepare('SELECT * FROM training_materials WHERE id=?').bind(Number(id)).first();
   if(!row||(row.status!=='published'&&data.role!=='boss'))return reply({error:'Матеріал не знайдено.'},404);
   return reply({material:{...row,blocks:JSON.parse(row.blocks)}});
  }
  if(data.role!=='boss')return reply({error:'Лише для ролі «Крутий бос».'},403);
  if(parts.length===1&&method==='POST'){
   const b=await request.json(),title=String(b.title||'').trim().slice(0,180),summary=String(b.summary||'').trim().slice(0,500);
   if(!title)return reply({error:'Вкажіть назву.'},400);
   const blocks=cleanBlocks(b.blocks),status=b.status==='published'?'published':'draft',now=new Date().toISOString();
   const result=await db.prepare('INSERT INTO training_materials(title,summary,blocks,status,created_at,updated_at) VALUES(?,?,?,?,?,?)').bind(title,summary,JSON.stringify(blocks),status,now,now).run();
   return reply({ok:true,id:result.meta.last_row_id},201);
  }
  if(parts.length===2&&validId(id)&&method==='PUT'){
   const b=await request.json(),title=String(b.title||'').trim().slice(0,180),summary=String(b.summary||'').trim().slice(0,500);
   if(!title)return reply({error:'Вкажіть назву.'},400);
   const blocks=cleanBlocks(b.blocks),status=b.status==='published'?'published':'draft';
   const result=await db.prepare('UPDATE training_materials SET title=?,summary=?,blocks=?,status=?,updated_at=? WHERE id=?').bind(title,summary,JSON.stringify(blocks),status,new Date().toISOString(),Number(id)).run();
   return result.meta.changes?reply({ok:true}):reply({error:'Матеріал не знайдено.'},404);
  }
  if(parts.length===2&&validId(id)&&method==='DELETE'){
   const result=await db.prepare('DELETE FROM training_materials WHERE id=?').bind(Number(id)).run();
   return result.meta.changes?reply({ok:true}):reply({error:'Матеріал не знайдено.'},404);
  }
  return reply({error:'Метод не підтримується.'},405);
 }catch(e){console.error('Materials API',e);return reply({error:e instanceof SyntaxError?'Неправильні дані.':e.message?.startsWith('D1_')?'Виконайте SQL-міграцію навчальних матеріалів.':e.message||'Помилка збереження.'},400)}
}
