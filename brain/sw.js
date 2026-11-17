/* Brain UJN PWA — no sensitive content is stored offline. */
"use strict";
self.addEventListener("install",event=>{event.waitUntil(self.skipWaiting())});
self.addEventListener("activate",event=>{event.waitUntil((async()=>{const keys=await caches.keys();await Promise.all(keys.filter(x=>x.startsWith("brain-ujn-")).map(x=>caches.delete(x)));await self.clients.claim()})())});
self.addEventListener("fetch",event=>{
 const request=event.request;
 if(request.mode!=="navigate"||request.method!=="GET")return;
 const url=new URL(request.url);
 if(url.origin!==self.location.origin||!url.pathname.startsWith(new URL(self.registration.scope).pathname))return;
 event.respondWith(fetch(request,{cache:"no-store"}).catch(()=>new Response('<!doctype html><html lang="pt-BR"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#142c3b"><title>Brain UJN — conexão necessária</title><body style="font:16px system-ui;margin:0;padding:12vh 24px;background:#f7f8fa;color:#142c3b;text-align:center"><h1>Conexão necessária</h1><p>Conecte-se à internet para acessar o Brain UJN com segurança.</p><button onclick="location.reload()" style="padding:12px 24px;border:0;border-radius:9px;background:#087e8b;color:white">Tentar novamente</button></body></html>',{status:503,headers:{"content-type":"text/html;charset=utf-8","cache-control":"no-store","x-content-type-options":"nosniff"}})));
});
