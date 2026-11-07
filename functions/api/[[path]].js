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
