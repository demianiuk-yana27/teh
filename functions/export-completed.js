import {recordExport} from './_dashboard-log.js';
const answer=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
export async function onRequest({request,env}){
 if(request.method!=='POST')return answer({error:'Method not allowed'},405);
 if(!env.EXPORT_EVENT_SECRET||!env.TASKS_DB)return answer({error:'Export event integration not configured'},503);
 const supplied=request.headers.get('X-Export-Secret')||'';
 const a=new TextEncoder().encode(supplied),b=new TextEncoder().encode(env.EXPORT_EVENT_SECRET);
 if(!supplied||a.length!==b.length)return answer({error:'Unauthorized'},401);
 let diff=0;for(let i=0;i<a.length;i++)diff|=a[i]^b[i];
 if(diff)return answer({error:'Unauthorized'},401);
 const data=await request.json().catch(()=>null);
 const sections=['КТВ','Відгуки','Доробки','Негативні відгуки','Звіт по кількості замовлень'];
 if(!data||!sections.includes(data.section)||!(/^[a-f0-9]{32}$/.test(data.run_id||''))||!Number.isSafeInteger(data.count)||data.count<0||typeof data.unit!=='string'||data.unit.length>40)return answer({error:'Invalid event'},400);
 try{await recordExport(env.TASKS_DB,data.section,data.run_id,data.count,data.unit,String(data.message||'').slice(0,300));return answer({ok:true})}
 catch(e){console.error('Export webhook failed',e);return answer({error:'Storage failure'},500)}
}
