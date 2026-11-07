import {recordExport} from '../_dashboard-log.js';
const BACKEND = 'https://teh-new.onrender.com';

export async function onRequest(context) {
  const incoming = new URL(context.request.url);
  const path = context.params.path;
  const suffix = Array.isArray(path) ? path.join('/') : (path || '');
  const target = new URL('/' + suffix, BACKEND);
  target.search = incoming.search;

  const headers = new Headers(context.request.headers);
  headers.delete('host');
  headers.delete('cf-connecting-ip');
  headers.delete('cf-ray');
  headers.delete('cf-visitor');

  const init = {
    method: context.request.method,
    headers,
    redirect: 'follow'
  };

  if (!['GET', 'HEAD'].includes(context.request.method)) {
    init.body = context.request.body;
  }

  try {
    const response = await fetch(target.toString(), init);
    const outHeaders = new Headers(response.headers);
    outHeaders.delete('content-encoding');
    outHeaders.delete('content-length');
    if(response.ok && context.data.role && context.env.TASKS_DB){
      const raw=await response.clone().json().catch(()=>null);
      if(raw?.status==='success' && (suffix==='status'||suffix==='negative/status')){
        const section=suffix==='status'?({'1':'КТВ','3':'Відгуки','4':'Доробки'}[String(raw.process_num)]):'Негативні відгуки';
        if(section)await recordExport(context.env.TASKS_DB,section,raw.run_id,raw.count,raw.unit,raw.message||'');
      }
      if(suffix==='operations/order-count-report'&&raw?.status==='success'){
        // The report counts status categories, not exported orders: no fabricated order count.
        // It is a synchronous confirmed completion, recorded with an explicitly different unit.
        const m=String(raw.message||'').match(/Записано статусів:\s*(\d+)/);
        if(m)await recordExport(context.env.TASKS_DB,'Звіт по кількості замовлень',crypto.randomUUID(),Number(m[1]),'статусів',raw.message||'');
      }
    }
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: outHeaders
    });
  } catch (error) {
    return Response.json(
      { status: 'error', message: 'Не вдалося з’єднатися з сервером автоматизацій.' },
      { status: 502 }
    );
  }
}
