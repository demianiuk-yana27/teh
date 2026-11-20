export const redirectUri='https://teh-7rt.pages.dev/quick-requests/oauth/callback';
export const configured=env=>Boolean(env.GOOGLE_OAUTH_CLIENT_ID&&env.GOOGLE_OAUTH_CLIENT_SECRET&&env.OAUTH_TOKEN_ENCRYPTION_KEY&&env.TASKS_DB);
const b64=bytes=>btoa(String.fromCharCode(...new Uint8Array(bytes)));
const unb64=s=>Uint8Array.from(atob(s),c=>c.charCodeAt(0));
async function key(env){const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(env.OAUTH_TOKEN_ENCRYPTION_KEY));return crypto.subtle.importKey('raw',hash,'AES-GCM',false,['encrypt','decrypt'])}
export async function seal(env,value){const iv=crypto.getRandomValues(new Uint8Array(12));const ct=await crypto.subtle.encrypt({name:'AES-GCM',iv},await key(env),new TextEncoder().encode(value));return b64(iv)+'.'+b64(ct)}
export async function unseal(env,value){const [iv,ct]=value.split('.');const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:unb64(iv)},await key(env),unb64(ct));return new TextDecoder().decode(plain)}
export async function exchange(env,fields){const body=new URLSearchParams({...fields,client_id:env.GOOGLE_OAUTH_CLIENT_ID,client_secret:env.GOOGLE_OAUTH_CLIENT_SECRET});const res=await fetch('https://oauth2.googleapis.com/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body});const data=await res.json();if(!res.ok||!data.access_token)throw Error(data.error_description||data.error||'Google token exchange failed');return data}
// Reuse short-lived OAuth access tokens within a warm Cloudflare isolate.
// Avoid a D1 read, AES decryption and Google token refresh for every request.
let cachedAccessToken=null;
let cachedUntil=0;
let pendingToken=null;
export async function accessToken(env){
 if(!configured(env))throw Error('OAuth не налаштовано в Cloudflare');
 if(cachedAccessToken&&Date.now()<cachedUntil)return cachedAccessToken;
 if(pendingToken)return pendingToken;
 pendingToken=(async()=>{
  const row=await env.TASKS_DB.prepare('SELECT encrypted_refresh_token FROM google_oauth_tokens WHERE id=1').first();
  if(!row)throw Error('Потрібно підключити Google через адмін-сторінку');
  const refresh_token=await unseal(env,row.encrypted_refresh_token);
  const token=await exchange(env,{grant_type:'refresh_token',refresh_token});
  cachedAccessToken=token.access_token;
  // Refresh well before expiry; a new worker isolate starts with an empty cache.
  cachedUntil=Date.now()+Math.max(0,(Number(token.expires_in)||3600)-300)*1000;
  return cachedAccessToken;
 })();
 try{return await pendingToken}finally{pendingToken=null}
}
