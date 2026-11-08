// Dedicated machine-only Prom session reader. No public cookie upload route.
// Deploy separately as a Cloudflare Worker with TASKS_DB D1 binding.
const json=(body,status=200)=>Response.json(body,{status,headers:{"Cache-Control":"no-store","X-Content-Type-Options":"nosniff"}});
const bytes=new TextEncoder();
function equal(a,b){const x=bytes.encode(a),y=bytes.encode(b);let d=x.length^y.length;for(let i=0;i<Math.max(x.length,y.length);i++)d|=(x[i]||0)^(y[i]||0);return d===0;}
function decode(s){return Uint8Array.from(atob(s),c=>c.charCodeAt(0));}
export default {
  async fetch(request,env){
    const url=new URL(request.url);
    if(request.method!=="GET"||url.pathname!=="/prom-session"||url.search)
      return json({error:"not found"},404);
    const auth=request.headers.get("Authorization")||"";
    const token=auth.match(/^Bearer ([^\s]+)$/i)?.[1]||"";
    if(!env.PROM_SESSION_MACHINE_TOKEN||!token||!equal(token,env.PROM_SESSION_MACHINE_TOKEN))
      return json({error:"unauthorized"},401);
    if(!env.TASKS_DB||!env.PROM_SESSION_ENCRYPTION_KEY)
      return json({error:"vault unavailable"},503);
    try {
      const row=await env.TASKS_DB.prepare("SELECT nonce,ciphertext FROM prom_session_vault WHERE id=1").first();
      if(!row)return json({error:"session not stored"},404);
      const keyBytes=decode(env.PROM_SESSION_ENCRYPTION_KEY);
      if(keyBytes.length!==32)throw Error("invalid key");
      const key=await crypto.subtle.importKey("raw",keyBytes,{name:"AES-GCM"},false,["decrypt"]);
      const plain=await crypto.subtle.decrypt({name:"AES-GCM",iv:decode(row.nonce)},key,decode(row.ciphertext));
      const cookies=JSON.parse(new TextDecoder().decode(plain));
      if(!Array.isArray(cookies))throw Error("invalid payload");
      return json({cookies});
    }catch(e){
      console.error("Prom vault read failed:",e?.name||"Error");
      return json({error:"vault unavailable"},503);
    }
  }
};
