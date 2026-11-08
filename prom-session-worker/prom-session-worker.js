// Dedicated machine-only reader and authenticated one-time migration receiver.
// Configure TASKS_DB, PROM_WORKER_ENCRYPTION_KEY, PROM_MIGRATION_TOKEN.
const enc=new TextEncoder(),dec=new TextDecoder();
const reply=(body,status=200)=>Response.json(body,{status,headers:{"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}});
const b64=a=>btoa(String.fromCharCode(...a));
const unb64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
const sha=async s=>new Uint8Array(await crypto.subtle.digest("SHA-256",enc.encode(s)));
function same(a,b){if(a.length!==b.length)return false;let n=0;for(let i=0;i<a.length;i++)n|=a[i]^b[i];return n===0;}
async function key(env){const raw=unb64(env.PROM_WORKER_ENCRYPTION_KEY||"");if(raw.length!==32)throw Error("invalid key");return crypto.subtle.importKey("raw",raw,"AES-GCM",false,["encrypt","decrypt"]);}
async function init(db){await db.prepare("CREATE TABLE IF NOT EXISTS prom_worker_session_v1 (id INTEGER PRIMARY KEY CHECK(id=1), nonce TEXT NOT NULL, ciphertext TEXT NOT NULL, machine_hash TEXT NOT NULL, migrated_at TEXT NOT NULL)").run();}
export default {
 async fetch(request,env){
  const url=new URL(request.url);
  if(!env.TASKS_DB)return reply({error:"vault unavailable"},503);
  if(request.method==="POST"&&url.pathname==="/__internal/migrate"&&!url.search){
   // This path is publicly reachable; a distinct high-entropy migration secret is mandatory.
   const supplied=(request.headers.get("X-Prom-Migration-Token")||"");
   if(!env.PROM_MIGRATION_TOKEN||!supplied||!same(await sha(supplied),await sha(env.PROM_MIGRATION_TOKEN)))
    return reply({error:"unauthorized"},401);
   try{
    const raw=await request.text();if(raw.length>150000)return reply({error:"payload too large"},413);
    const data=JSON.parse(raw);
    if(!Array.isArray(data.cookies)||!data.cookies.length||data.cookies.length>250||
       !data.cookies.every(c=>c&&typeof c.name==="string"&&typeof c.value==="string"&&typeof c.domain==="string"&&/(^|\\.)prom\\.ua$/i.test(c.domain.replace(/^\\./,"")))||
       typeof data.machineToken!=="string"||data.machineToken.length<24)return reply({error:"invalid payload"},400);
    const cryptoKey=await key(env),nonce=crypto.getRandomValues(new Uint8Array(12));
    const cipher=new Uint8Array(await crypto.subtle.encrypt({name:"AES-GCM",iv:nonce},cryptoKey,enc.encode(JSON.stringify(data.cookies))));
    const hash=b64(await sha(data.machineToken));
    await init(env.TASKS_DB);
    await env.TASKS_DB.prepare("INSERT INTO prom_worker_session_v1(id,nonce,ciphertext,machine_hash,migrated_at) VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET nonce=excluded.nonce,ciphertext=excluded.ciphertext,machine_hash=excluded.machine_hash,migrated_at=excluded.migrated_at").bind(b64(nonce),b64(cipher),hash,new Date().toISOString()).run();
    return reply({migrated:true,cookie_count:data.cookies.length});
   }catch(e){console.error("Migration failed:",e?.name||"Error");return reply({error:"migration unavailable"},503);}
  }
  if(request.method!=="GET"||url.pathname!=="/prom-session"||url.search)return reply({error:"not found"},404);
  const match=(request.headers.get("Authorization")||"").match(/^Bearer ([^\\s]+)$/i);
  if(!match)return reply({error:"unauthorized"},401);
  try{
   await init(env.TASKS_DB);
   const row=await env.TASKS_DB.prepare("SELECT nonce,ciphertext,machine_hash FROM prom_worker_session_v1 WHERE id=1").first();
   if(!row)return reply({error:"session not migrated"},404);
   if(!same(await sha(match[1]),unb64(row.machine_hash)))return reply({error:"unauthorized"},401);
   const plain=await crypto.subtle.decrypt({name:"AES-GCM",iv:unb64(row.nonce)},await key(env),unb64(row.ciphertext));
   const cookies=JSON.parse(dec.decode(plain));
   return reply({cookies});
  }catch(e){console.error("Vault read failed:",e?.name||"Error");return reply({error:"vault unavailable"},503);}
 }
};
