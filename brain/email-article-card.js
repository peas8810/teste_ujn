/* Brain UJN — identificação editorial na Central de E-mails.
   Usa a sessão do painel e a API ujn-email-desk-v1. Sem credenciais no cliente. */
(function(){
"use strict";
const checked = new Set();
const busy = new Set();
const allowedHosts = new Set(["doi.org","www.doi.org","remunom.ojsbr.com","jrnm.ojsbr.com","rsv.ojsbr.com","jirrs.org.uk","nexussr.org.uk"]);
const base = document.getElementById("mailDeskArticleIdentity");
const refresh = document.getElementById("mailDeskArticleIdentityRefresh");
if(!base || !refresh) return;
const style = document.createElement("style");
style.textContent = ".brain-article-list{display:grid;gap:10px;margin-top:9px}.brain-article-card{padding:13px;border:1px solid #d5e3e9;border-left:3px solid #078692;border-radius:10px;background:#fbfdfe}.brain-article-title{display:block;margin:4px 0 8px;font-size:14px;line-height:1.45;color:#183c50}.brain-article-meta{display:flex;flex-wrap:wrap;gap:6px 15px;font-size:12px;color:#496477}.brain-article-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.brain-article-actions a{display:inline-flex;padding:7px 10px;border-radius:7px;border:1px solid #b5d5df;font-size:12px;font-weight:650;color:#086e80;text-decoration:none}.brain-article-actions a:hover{background:#e8f5f7}.brain-article-note{margin:6px 0 0;font-size:12px;color:#637584}.brain-article-status{display:inline-block;font-size:11px;font-weight:650;padding:3px 7px;border-radius:6px;background:#e4f2ef;color:#176a59}.brain-article-status.review{background:#fff4df;color:#885e18}.brain-article-muted{color:#637584;font-size:13px;margin:5px 0}";
document.head.appendChild(style);
const child = (tag,value,cls) => {const n=document.createElement(tag);if(value!==undefined && value!==null)n.textContent=String(value);if(cls)n.className=cls;return n;};
const validUrl = raw => {try{const u=new URL(String(raw||""));return u.protocol==="https:" && !u.username && !u.password && allowedHosts.has(u.hostname.toLowerCase())?u.toString():null}catch{return null}};
const articleKey = x => String(x.journal_code||"")+":"+String(x.submission_id||"");
function action(target,label,url) {
 const safe=validUrl(url);
 if(!safe)return;
 const a=child("a",label);a.href=safe;a.target="_blank";a.rel="noopener noreferrer";a.referrerPolicy="no-referrer";target.append(a);
}
function merge(cached,found) {
 const all=new Map();
 for(const item of [...(cached||[]),...(found||[])]) {
  if(!item || !item.journal_code || !item.submission_id)continue;
  const k=articleKey(item),prev=all.get(k);
  // Retain DOI, public URL, title and provenance when later lookups are partial.
  const x=prev?{...prev,...item}:item;
  if(prev){for(const prop of ["doi","article_url","consultation_url","article_title","title","verified_at"])if(!x[prop]&&prev[prop])x[prop]=prev[prop]}
  all.set(k,x);
 }
 return [...all.values()].slice(0,8);
}
function render(items,notice="",kind="info") {
 base.replaceChildren();
 if(notice)base.append(child("p",notice,kind==="warning"?"brain-article-note":"brain-article-muted"));
 if(!items?.length) {
  if(!notice)base.append(child("p","Nenhum artigo identificado nesta conversa. A busca automática será iniciada ao abrir o e-mail.","brain-article-muted"));
  return;
 }
 const list=child("div",undefined,"brain-article-list");
 for(const item of items){
  const card=child("article",undefined,"brain-article-card");
  const head=child("div");
  head.append(child("strong",(item.journal_code||"Revista")+" · Submissão #"+item.submission_id));
  const source=String(item.match_source||"");
  const verified=source==="ojs_api" || Boolean(item.verified_at);
  const status=child("span",verified?"Dados consultados no OJS":"Conferir correspondência","brain-article-status"+(verified?"":" review"));
  status.style.marginLeft="8px";head.append(status);card.append(head);
  const title=item.article_title||item.title||"Título ainda não recuperado";
  card.append(child("strong",title,"brain-article-title"));
  const meta=child("div",undefined,"brain-article-meta");
  const state=item.editorial_status||item.status||"";
  if(state)meta.append(child("span","Situação: "+({"published":"Publicado","editorial":"Em fluxo editorial","catalog":"Catálogo","unverified":"Aguardando verificação"}[state]||state)));
  if(item.doi)meta.append(child("span","DOI: "+item.doi));
  if(item.confidence!==undefined && item.confidence!==null && Number(item.confidence)<0.89)meta.append(child("span","Associação sujeita a revisão"));
  card.append(meta);
  const links=child("div",undefined,"brain-article-actions");
  // OJS URL should only be presented when supplied, not inferred for unpublished submissions.
  if(item.article_url)action(links,"Abrir artigo",item.article_url);
  const doi=String(item.doi||"").trim();
  if(/^10\.\d{4,9}\/\S{3,150}$/i.test(doi))action(links,"Abrir DOI","https://doi.org/"+doi);
  if(item.consultation_url)action(links,"Consulta da revista",item.consultation_url);
  if(links.childElementCount)card.append(links);
  if(!verified)card.append(child("p","O vínculo editorial não comprova autoria ou publicação. Confira no OJS antes de responder ao autor.","brain-article-note"));
  list.append(card);
 }
 base.append(list);
}
async function resolve(threadId,cached=[],force=false) {
 if(!threadId || busy.has(threadId) || (!force && checked.has(threadId)))return;
 checked.add(threadId);busy.add(threadId);
 if(window.MAILDESK?.selected===threadId || (typeof MAILDESK!=="undefined"&&MAILDESK.selected===threadId)){
  refresh.disabled=true;
  render(cached,"Pesquisando título, revista e vínculo editorial no OJS…");
 }
 try {
  const result=await mailDeskCall("article_resolve",{thread_id:threadId});
  if(typeof MAILDESK!=="undefined" && MAILDESK.selected!==threadId)return;
  const matches=Array.isArray(result.matches)?result.matches:[];
  const rows=merge(cached,matches);
  if(MAILDESK.currentThreadData)MAILDESK.currentThreadData.article_identifications=rows;
  let message="";
  if(result.matching_status==="review")message="Foram encontrados possíveis artigos. Confira a correspondência antes de utilizá-la.";
  else if(!rows.length)message="Não foi possível confirmar um artigo com os dados disponíveis nesta conversa. Use “Adicionar artigo” para vincular manualmente.";
  else if(result.lookups_attempted?.some(x=>x.state!=="ok"))message="Os dados identificados estão disponíveis, mas algumas consultas OJS não foram concluídas.";
  render(rows,message,message?"warning":"info");
 } catch(error) {
  if(typeof MAILDESK!=="undefined" && MAILDESK.selected!==threadId)return;
  render(cached,"A consulta automática não foi concluída. Você pode tentar novamente ou usar “Adicionar artigo”.","warning");
 } finally {
  busy.delete(threadId);
  if(typeof MAILDESK!=="undefined" && MAILDESK.selected===threadId)refresh.disabled=false;
 }
}
window.brainMailArticleOpen = (threadId,data) => {
 const cached=Array.isArray(data?.article_identifications)?data.article_identifications:[];
 refresh.disabled=false;
 render(cached);
 if(!cached.length)void resolve(threadId,cached,false);
};
window.brainMailArticleClear = () => {
 refresh.disabled=true;
 render([],"Carregando informações editoriais da conversa…");
};
refresh.addEventListener("click",()=>{
 if(typeof MAILDESK==="undefined" || !MAILDESK.selected)return;
 const cached=MAILDESK.currentThreadData?.article_identifications||[];
 void resolve(MAILDESK.selected,cached,true);
});
})();