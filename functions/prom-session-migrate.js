// Boss-only, same-origin migration of existing encrypted Prom session to a
// separately bound Worker. Does not delete or modify the original vault.
const json=(body,status=200)=>Response.json(body,{status,headers:{"Cache-Control":"no-store"}});
const unb64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
export async function onRequest({request,env,data}){
 if(request.method!=="POST")return json({error:"method not allowed"},405);
 if(data.role!=="boss")return json({error:"forbidden"},403);
 if(request.headers.get("Origin")!==new URL(request.url).origin)return json({error:"invalid origin"},403);
 if(!env.PROM_READER||!env.TASKS_DB||!env.PROM_SESSION_ENCRYPTION_KEY||
    !env.PROM_SESSION_MACHINE_TOKEN||!env.PROM_MIGRATION_TOKEN)
   return json({error:"migration configuration incomplete"},503);
 try{
  const row=await env.TASKS_DB.prepare("SELECT nonce,ciphertext FROM prom_session_vault WHERE id=1").first();
  if(!row)return json({error:"no stored session"},404);
  const raw=unb64(env.PROM_SESSION_ENCRYPTION_KEY);
  if(raw.length!==32)throw Error("invalid key");
  const key=await crypto.subtle.importKey("raw",raw,"AES-GCM",false,["decrypt"]);
  const plain=await crypto.subtle.decrypt({name:"AES-GCM",iv:unb64(row.nonce)},key,unb64(row.ciphertext));
  const cookies=JSON.parse(new TextDecoder().decode(plain));
  if(!Array.isArray(cookies)||!cookies.length)throw Error("invalid cookies");
  // Service Binding: internal Cloudflare invocation, no public pages.dev HTTP hop.
  const response=await env.PROM_READER.fetch("https://prom-reader.internal/__internal/migrate",{
   method:"POST",
   headers:{"Content-Type":"application/json","X-Prom-Migration-Token":env.PROM_MIGRATION_TOKEN},
   body:JSON.stringify({cookies,machineToken:env.PROM_SESSION_MACHINE_TOKEN})
  });
  if(!response.ok)return json({error:"Worker migration failed",worker_status:response.status},502);
  return json({migrated:true});
 }catch(e){
  console.error("Prom migration failed:",e?.name||"Error");
  return json({error:"migration unavailable"},503);
 }
}
