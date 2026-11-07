import {record} from '../_dashboard-log.js';
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
    if(context.data.role==='boss'&&context.request.method==='POST'&&response.ok){
      const match=suffix.match(/^run\/(1|2|3|4)$/),neg=suffix.match(/^negative\/run\/(reviews|analytics)$/);
      const section=match?({'1':'КТВ','2':'КТВ','3':'Відгуки','4':'Доробки'}[match[1]]):neg?'Негативні відгуки':suffix==='operations/order-count-report'?'Звіт по кількості замовлень':null;
      if(section){const raw=await response.clone().json().catch(()=>({}));if(raw.status==='started'||raw.status==='success'||raw.status==='ok')await record(context.env.TASKS_DB,section,'Запуск вигрузки',raw.status,'Крутий бос',raw.message||'');}
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
