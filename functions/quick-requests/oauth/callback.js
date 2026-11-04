import {configured,redirectUri,exchange,seal} from '../oauth-helper.js';
const html=(msg,ok=false)=>new Response('<!doctype html><html lang="uk"><meta charset="utf-8"><title>Google OAuth</title><body style="font:16px system-ui;padding:40px;max-width:650px;margin:auto"><h2>'+ (ok?'✅ Google підключено':'⚠️ Не вдалося підключити Google') +'</h2><p>'+msg+'</p><a href="/">Повернутися на сайт</a></body></html>',{status:ok?200:400,headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Set-Cookie':'teh_oauth_state=; Path=/quick-requests/oauth; Max-Age=0; HttpOnly; Secure; SameSite=Lax'}});
export async function onRequestGet({request,env,data}){
 if(data.role!=='boss')return html('Увійдіть на сайт як адміністратор.');
 if(!configured(env))return html('OAuth ще не налаштовано.');
 const u=new URL(request.url),state=u.searchParams.get('state'),code=u.searchParams.get('code'),cookie=request.headers.get('Cookie')||'';
 const match=cookie.match(/(?:^|;\s*)teh_oauth_state=([^;]+)/);
 if(!state||!match||state!==match[1]||!code)return html('Авторизацію скасовано або перевірка безпеки не пройшла. Спробуйте знову.');
 try{
 const d=await exchange(env,{grant_type:'authorization_code',code,redirect_uri:redirectUri});
 if(!d.refresh_token)return html('Google не повернув дозвіл для тривалої роботи. Повторіть підключення.');
 const encrypted=await seal(env,d.refresh_token);
 await env.TASKS_DB.prepare('INSERT INTO google_oauth_tokens (id,encrypted_refresh_token,updated_at) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET encrypted_refresh_token=excluded.encrypted_refresh_token,updated_at=excluded.updated_at').bind(encrypted,new Date().toISOString()).run();
 return html('Доступ до Google Sheets збережено. Тепер можна надсилати запити з сайту.',true);
 }catch(e){console.error('OAuth callback failed',e);return html('Помилка обміну токеном або збереження в базу. Перевірте налаштування Cloudflare та міграцію D1.')}
}
