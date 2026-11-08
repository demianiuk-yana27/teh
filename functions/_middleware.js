const enc = new TextEncoder();

function b64url(bytes) {
  let s = '';
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function sign(role, secret) {
  const key = await crypto.subtle.importKey('raw', enc.encode(secret), {name:'HMAC', hash:'SHA-256'}, false, ['sign']);
  const sig = await crypto.subtle.sign('HMAC', key, enc.encode(role));
  return role + '.' + b64url(new Uint8Array(sig));
}

async function roleFromRequest(request, env) {
  const cookie = request.headers.get('Cookie') || '';
  const m = cookie.match(/(?:^|;\s*)asteril_role=([^;]+)/);
  if (!m) return null;
  const token = decodeURIComponent(m[1]);
  const dot = token.indexOf('.');
  if (dot < 1) return null;
  const role = token.slice(0, dot);
  if (!['manager','boss'].includes(role)) return null;
  const secret = `${env.MANAGER_PASSWORD || ''}|${env.BOSS_PASSWORD || ''}|asteril-access-v1`;
  if (!env.MANAGER_PASSWORD || !env.BOSS_PASSWORD) return null;
  const expected = await sign(role, secret);
  return token === expected ? role : null;
}

export async function onRequest(context) {
  const {request, env, next} = context;
  const url = new URL(request.url);
  const path = url.pathname;

  if (path === '/auth/login' && request.method === 'POST') {
    if (!env.MANAGER_PASSWORD || !env.BOSS_PASSWORD) {
      return Response.json({status:'error', message:'Паролі доступу ще не налаштовані в Cloudflare.'}, {status:503});
    }
    let body = {};
    try { body = await request.json(); } catch (_) {}
    const password = String(body.password || '');
    let role = null;
    if (password === env.BOSS_PASSWORD) role = 'boss';
    else if (password === env.MANAGER_PASSWORD) role = 'manager';
    if (!role) return Response.json({status:'error', message:'Невірний пароль.'}, {status:401});
    const secret = `${env.MANAGER_PASSWORD}|${env.BOSS_PASSWORD}|asteril-access-v1`;
    const token = await sign(role, secret);
    return Response.json({status:'ok', role}, {headers:{'Set-Cookie':`asteril_role=${encodeURIComponent(token)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=43200`}});
  }

  if (path === '/auth/logout' && request.method === 'POST') {
    return Response.json({status:'ok'}, {headers:{'Set-Cookie':'asteril_role=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0'}});
  }

  // Dedicated machine-to-machine endpoint authenticates its own secret.
  if(path==='/export-completed')return next();
  // Machine access to the encrypted Prom vault uses a separate bearer token.
  if(path==='/prom-session' && request.method==='GET' && request.headers.has('Authorization'))return next();
  if(path==='/prom-session-transfer' && request.method==='PUT')return next();
  const role = await roleFromRequest(request, env);
  if (path === '/auth/me') return Response.json(role ? {authenticated:true, role} : {authenticated:false}, {status: role ? 200 : 401});

  const publicAsset = path === '/login.html' || path === '/privacy.html' || /\.(?:js|css|png|jpg|jpeg|gif|svg|ico|webp|json)$/i.test(path);
  if (!role && !publicAsset) return Response.redirect(new URL('/login.html', url), 302);

  if (path.startsWith('/api/') && request.method !== 'GET' && request.method !== 'HEAD' && role !== 'boss') {
    return Response.json({status:'forbidden', message:'Ця дія доступна лише для ролі «Крутий бос».'}, {status:403});
  }

  context.data.role = role;
  const response = await next();
  const headers = new Headers(response.headers);
  if (role) headers.set('X-Asteril-Role', role);
  return new Response(response.body, {status:response.status, statusText:response.statusText, headers});
}
