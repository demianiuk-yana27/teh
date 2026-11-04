import {configured,redirectUri} from '../oauth-helper.js';
const encode=x=>btoa(String.fromCharCode(...new Uint8Array(x))).replace(/=/g,'').replace(/\+/g,'-').replace(/\//g,'_');
export async function onRequestGet({request,env,data}){
 if(data.role!=='boss')return Response.json({error:'Доступ лише для адміністратора'}, {status:403});
 if(!configured(env))return Response.json({error:'Додайте GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, OAUTH_TOKEN_ENCRYPTION_KEY і TASKS_DB'}, {status:503});
 const state=encode(crypto.getRandomValues(new Uint8Array(32)));
 const url=new URL('https://accounts.google.com/o/oauth2/v2/auth');
 for(const [k,v] of Object.entries({client_id:env.GOOGLE_OAUTH_CLIENT_ID,redirect_uri:redirectUri,response_type:'code',scope:'https://www.googleapis.com/auth/spreadsheets',access_type:'offline',prompt:'consent',state}))url.searchParams.set(k,v);
 return new Response(null,{status:302,headers:{Location:url.toString(),'Set-Cookie':'teh_oauth_state='+state+'; HttpOnly; Secure; SameSite=Lax; Path=/quick-requests/oauth; Max-Age=600','Cache-Control':'no-store'}});
}
