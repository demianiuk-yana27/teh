const json=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
const bytes=new TextEncoder();
const hex=a=>Array.from(a,b=>b.toString(16).padStart(2,'0')).join('');
async function hash(s){return hex(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes.encode(s))));}
const b64=a=>btoa(String.fromCharCode(...a));
function cookiesValid(c){return Array.isArray(c)&&c.length>0&&c.length<=250&&c.every(x=>x&&typeof x.name==='string'&&x.name.length>0&&typeof x.value==='string'&&typeof x.domain==='string'&&(/^\\.?prom\\.ua$/i.test(x.domain)||/^\\.?[a-z0-9.-]+\\.prom\\.ua$/i.test(x.domain)));}
async function key(env){const raw=Uint8Array.from(atob(env.PROM_SESSION_ENCRYPTION_KEY||''),c=>c.charCodeAt(0));if(raw.length!==32)throw Error('key');return crypto.subtle.importKey('raw',raw,'AES-GCM',false,['encrypt']);}
export async function onRequest({request,env,data}){
 const method=request.method;
 if(!env.TASKS_DB)return json({error:'D1 binding missing'},503);
 try{
  const db=env.TASKS_DB;
  await db.prepare('CREATE TABLE IF NOT EXISTS prom_session_transfer (id INTEGER PRIMARY KEY CHECK(id=1), token_hash TEXT NOT NULL, expires_at INTEGER NOT NULL)').run();
  if(method==='GET'){
   if(data.role!=='boss')return json({error:'forbidden'},403);
   return new Response(`<!doctype html><html lang="uk"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Підключення Prom</title><style>body{font:16px system-ui;max-width:650px;margin:5vh auto;padding:20px}button{padding:12px 18px;cursor:pointer}code{overflow-wrap:anywhere;font-size:20px}p{line-height:1.5}</style><h2>Захищене підключення Prom</h2><p>Натисніть кнопку, щоб створити одноразовий код на 5 хвилин. Вставте його лише в локальний інструмент на MacBook. Код не є паролем Prom.</p><button id="make">Створити одноразовий код</button><p id="status"></p><code id="code"></code><script>document.getElementById('make').onclick=async()=>{const status=document.getElementById('status');document.getElementById('code').textContent='';status.textContent='Створюємо код…';try{const r=await fetch('/prom-session-transfer',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:'{}'});const d=await r.json();if(!r.ok)throw Error(d.error||'Помилка');document.getElementById('code').textContent=d.code;status.textContent='Код діє 5 хвилин, використовується один раз.'}catch(e){status.textContent=e.message}};</script></html>`,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"}});
  }
  if(method==='POST'){
   if(data.role!=='boss')return json({error:'forbidden'},403);
   if(request.headers.get('Origin')!==new URL(request.url).origin)return json({error:'origin'},403);
   const code=hex(crypto.getRandomValues(new Uint8Array(24)));
   await db.prepare('INSERT INTO prom_session_transfer(id,token_hash,expires_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET token_hash=excluded.token_hash,expires_at=excluded.expires_at').bind(await hash(code),Date.now()+5*60*1000).run();
   return json({code,expires_in_seconds:300});
  }
  if(method!=='PUT')return json({error:'method not allowed'},405);
  const authorization=request.headers.get('Authorization')||'';
  if(!/^Bearer [a-f0-9]{48}$/i.test(authorization))return json({error:'unauthorized'},401);
  const digest=await hash(authorization.slice(7).toLowerCase());
  // Consume the one-time code atomically, before processing the sensitive payload.
  const consumed=await db.prepare('DELETE FROM prom_session_transfer WHERE id=1 AND token_hash=? AND expires_at>?').bind(digest,Date.now()).run();
  if(consumed.meta?.changes!==1)return json({error:'code expired or used'},401);
  const raw=await request.text();
  if(raw.length>150000)return json({error:'payload too large'},413);
  let payload;try{payload=JSON.parse(raw)}catch{return json({error:'invalid json'},400)}
  if(!cookiesValid(payload.cookies))return json({error:'invalid cookies'},400);
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const ciphertext=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},await key(env),bytes.encode(JSON.stringify(payload.cookies))));
  await db.prepare('CREATE TABLE IF NOT EXISTS prom_session_vault (id INTEGER PRIMARY KEY CHECK(id=1), nonce TEXT NOT NULL, ciphertext TEXT NOT NULL, updated_at TEXT NOT NULL)').run();
  await db.prepare('INSERT INTO prom_session_vault(id,nonce,ciphertext,updated_at) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET nonce=excluded.nonce,ciphertext=excluded.ciphertext,updated_at=excluded.updated_at').bind(b64(iv),b64(ciphertext),new Date().toISOString()).run();
  return json({stored:true,verified:false,cookie_count:payload.cookies.length});
 }catch{return json({error:'vault unavailable'},503)}
}
