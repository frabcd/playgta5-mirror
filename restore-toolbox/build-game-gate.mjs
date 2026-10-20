import { pbkdf2Sync, randomBytes } from 'node:crypto';
import { writeFileSync } from 'node:fs';
if (!process.env.GTA_PASSWORD) throw Error('GTA_PASSWORD must be supplied at packaging time');
const salt=randomBytes(24).toString('hex');
const passwordHash=pbkdf2Sync(process.env.GTA_PASSWORD,salt,10000,32,'sha256').toString('hex');
const sessionKey=randomBytes(32).toString('hex');
const constants=JSON.stringify({salt,passwordHash,sessionKey,origin:'https://9104c0b6.fran-abcd-abcd.pages.dev'});
const worker=`const config=${constants};
const enc=new TextEncoder();
const hex=bytes=>Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,'0')).join('');
async function sign(value){const key=await crypto.subtle.importKey('raw',enc.encode(config.sessionKey),{name:'HMAC',hash:'SHA-256'},false,['sign']);return hex(await crypto.subtle.sign('HMAC',key,enc.encode(value)));}
async function passwordMatches(password){if(typeof password!=='string'||password.length>256)return false;const key=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveBits']);const result=hex(await crypto.subtle.deriveBits({name:'PBKDF2',salt:enc.encode(config.salt),iterations:10000,hash:'SHA-256'},key,256));let diff=0;for(let i=0;i<result.length;i++)diff|=result.charCodeAt(i)^config.passwordHash.charCodeAt(i);return diff===0;}
function privateHeaders(extra={}){return {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',...extra};}
async function authenticated(request){const token=(request.headers.get('Cookie')||'').split(';').map(v=>v.trim()).find(v=>v.startsWith('fran_game_session='))?.slice('fran_game_session='.length)||'';const [expiry,signature]=token.split('.');return Boolean(expiry&&Number.isFinite(Number(expiry))&&Number(expiry)>Date.now()&&Number(expiry)<=Date.now()+28800000&&signature===await sign(expiry));}
function assetPath(path){return ['/b/','/data/','/__chunks/','/__support/'].some(prefix=>path.startsWith(prefix))||['/chunk-index.js','/chunk-fetch.js'].includes(path);}
export default {async fetch(request,env){const url=new URL(request.url);
if(url.pathname==='/api/game-unlock'){
 if(request.method!=='POST')return new Response('Method not allowed',{status:405});
 if(request.headers.get('Origin')!==url.origin)return new Response('Forbidden',{status:403});
 if(Number(request.headers.get('Content-Length')||0)>2048)return new Response('Too large',{status:413});
 const json=(request.headers.get('Content-Type')||'').includes('application/json');let body;try{body=json?await request.json():Object.fromEntries(await request.formData());}catch{return new Response('Invalid request',{status:400});}
 if(!await passwordMatches(body.password))return new Response('Incorrect password',{status:401,headers:privateHeaders()});
 const expiry=String(Date.now()+8*60*60*1000),token=expiry+'.'+await sign(expiry);
 return new Response(json?'OK':null,{status:json?200:303,headers:privateHeaders({'Set-Cookie':'fran_game_session='+token+'; Path=/; Max-Age=28800; HttpOnly; Secure; SameSite=Strict',...(json?{}:{Location:url.origin+'/calculator/gta-v/play'})})});
}
if(url.pathname==='/calculator/gta-v/play'){
 if(!await authenticated(request))return Response.redirect(url.origin+'/calculator/gta-v/',303);
 return new Response('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>洛圣都 · 计算器</title><style>body{margin:0;background:#111;color:white;font:14px Arial}nav{height:40px;display:flex;align-items:center;padding:0 16px;gap:20px}a{color:inherit}iframe{display:block;width:100%;height:calc(100svh - 40px);border:0}</style><nav><a href="/calculator">← 返回计算器</a><span>洛圣都 · 单人模式</span></nav><iframe src="/calculator/gta-v/frame?low=1&fps=30&res=1280x720&shadows=0" title="洛圣都单人游戏" allow="cross-origin-isolated; fullscreen; gamepad; autoplay" allowfullscreen></iframe></html>',{headers:privateHeaders({'Content-Type':'text/html; charset=utf-8','Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Embedder-Policy':'require-corp','Permissions-Policy':'cross-origin-isolated=(self)','Content-Security-Policy':"frame-ancestors 'self'"})});
}
const frame=url.pathname==='/calculator/gta-v/frame';
if(frame||assetPath(url.pathname)){
 if(!await authenticated(request))return frame?Response.redirect(url.origin+'/calculator/gta-v/',303):new Response('Unlock the game first',{status:401,headers:privateHeaders()});
 if(!['GET','HEAD'].includes(request.method))return new Response('Method not allowed',{status:405});
 const upstream=new URL(frame?'/':url.pathname,config.origin);upstream.search=url.search;
 const headers=new Headers();for(const name of ['Range','If-None-Match','If-Modified-Since','Accept']){if(request.headers.has(name))headers.set(name,request.headers.get(name));}
 const response=await fetch(upstream,{method:request.method,headers,redirect:'follow'});
 const result=new Headers(response.headers);
 result.set('Cross-Origin-Opener-Policy','same-origin');result.set('Cross-Origin-Embedder-Policy','require-corp');result.set('Cross-Origin-Resource-Policy','same-origin');result.set('X-Frame-Options','SAMEORIGIN');
 const policy=(result.get('Content-Security-Policy')||'').split(';').filter(v=>!v.trim().startsWith('frame-ancestors')).filter(Boolean);policy.push("frame-ancestors 'self'");result.set('Content-Security-Policy',policy.join('; '));
 if(frame&&request.method==='GET'&&response.ok){let html=await response.text();html=html.replace('<head>','<head><base href="/">');for(const name of ['Content-Length','Content-Encoding','ETag'])result.delete(name);result.set('Cache-Control','no-store');return new Response(html,{status:response.status,headers:result});}
 return new Response(response.body,{status:response.status,headers:result});
}
if(url.pathname==='/calculator/gta-v'||url.pathname==='/calculator/gta-v/'){
 const assetUrl=new URL('/gta-login',url),response=await env.ASSETS.fetch(new Request(assetUrl,request));const headers=new Headers(response.headers);headers.set('Cache-Control','no-store');return new Response(response.body,{status:response.status,headers});
}
return env.ASSETS.fetch(request);
}};
`;
writeFileSync('out/_worker.js',worker);
writeFileSync('out/_routes.json',JSON.stringify({version:1,include:['/api/game-unlock','/calculator/gta-v','/calculator/gta-v/*','/b/*','/data/*','/__chunks/*','/chunk-index.js','/chunk-fetch.js','/__support/*'],exclude:[]}));
console.log('Packaged server-verified calculator gate with authenticated same-origin game streaming.');
