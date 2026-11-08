const encoder = new TextEncoder();
const decoder = new TextDecoder();
const json = (body, status=200) => Response.json(body, {status, headers:{'Cache-Control':'no-store'}});
function constantTime(a,b) {
  const x=encoder.encode(a), y=encoder.encode(b);
  let diff=x.length ^ y.length;
  for(let i=0;i<Math.max(x.length,y.length);i++) diff |= (x[i]||0) ^ (y[i]||0);
  return diff===0;
}
async function keyFor(env) {
  const secret=env.PROM_SESSION_ENCRYPTION_KEY;
  if(!secret) throw Error('PROM_SESSION_ENCRYPTION_KEY is not configured');
  const raw=Uint8Array.from(atob(secret),c=>c.charCodeAt(0));
  if(raw.length!==32) throw Error('Encryption key must be 32 bytes');
  return crypto.subtle.importKey('raw',raw,{name:'AES-GCM'},false,['encrypt','decrypt']);
}
const b64 = bytes => btoa(String.fromCharCode(...bytes));
const unb64 = str => Uint8Array.from(atob(str),c=>c.charCodeAt(0));
async function dbFor(env) {
  if(!env.TASKS_DB) throw Error('TASKS_DB binding is missing');
  await env.TASKS_DB.prepare('CREATE TABLE IF NOT EXISTS prom_session_vault (id INTEGER PRIMARY KEY CHECK(id=1), nonce TEXT NOT NULL, ciphertext TEXT NOT NULL, updated_at TEXT NOT NULL)').run();
  return env.TASKS_DB;
}
async function encrypt(key, value) {
  const nonce=crypto.getRandomValues(new Uint8Array(12));
  const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv:nonce},key,encoder.encode(JSON.stringify(value)));
  return {nonce:b64(nonce),ciphertext:b64(new Uint8Array(ciphertext))};
}
async function decrypt(key,row) {
  const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:unb64(row.nonce)},key,unb64(row.ciphertext));
  return JSON.parse(decoder.decode(plain));
}
function validCookies(value) {
  return Array.isArray(value) && value.length>0 && value.length<=250 && value.every(c=>
    c && typeof c==='object' && typeof c.name==='string' && c.name.length>0 &&
    typeof c.value==='string' && typeof c.domain==='string' &&
    (c.domain.toLowerCase().replace(/^\./,'')==='prom.ua' || c.domain.toLowerCase().replace(/^\./,'').endsWith('.prom.ua'))
  );
}
export async function onRequest({request,env,data}) {
  const method=request.method;
  const machine=method==='GET' && request.headers.has('Authorization');
  if(machine) {
    const token=(request.headers.get('Authorization')||'').replace(/^Bearer\s+/i,'');
    if(!env.PROM_SESSION_MACHINE_TOKEN || !constantTime(token,env.PROM_SESSION_MACHINE_TOKEN)) return json({error:'unauthorized'},401);
  } else {
    if(data.role!=='boss') return json({error:'forbidden'},403);
    if(method!=='GET' && method!=='POST' && method!=='DELETE') return json({error:'method not allowed'},405);
    if(method!=='GET') {
      const origin=request.headers.get('Origin');
      if(!origin || origin!==new URL(request.url).origin) return json({error:'invalid origin'},403);
    }
  }
  try {
    const db=await dbFor(env);
    if(method==='GET') {
      const row=await db.prepare('SELECT nonce,ciphertext,updated_at FROM prom_session_vault WHERE id=1').first();
      if(!row) return json({connected:false},machine?404:200);
      if(!machine) return json({stored:true,verified:false,updated_at:row.updated_at});
      const cookies=await decrypt(await keyFor(env),row);
      return json({cookies});
    }
    if(method==='DELETE') {
      await db.prepare('DELETE FROM prom_session_vault WHERE id=1').run();
      return json({stored:false});
    }
    const length=Number(request.headers.get('content-length')||0);
    if(length>150000) return json({error:'payload too large'},413);
    const payload=await request.json();
    if(!validCookies(payload.cookies) || JSON.stringify(payload).length>150000) return json({error:'invalid cookie data'},400);
    const encrypted=await encrypt(await keyFor(env),payload.cookies);
    await db.prepare('INSERT INTO prom_session_vault(id,nonce,ciphertext,updated_at) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET nonce=excluded.nonce,ciphertext=excluded.ciphertext,updated_at=excluded.updated_at').bind(encrypted.nonce,encrypted.ciphertext,new Date().toISOString()).run();
    return json({stored:true,verified:false});
  } catch(e) {
    return json({error:'Session vault unavailable; check Cloudflare bindings and encryption key'},503);
  }
}
