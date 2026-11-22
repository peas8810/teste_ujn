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
  if(!notice)base.append(child("p","Nenhuma correspondência confirmada ainda. Você pode pesquisar pelo título extraído do anexo.","brain-article-muted"));
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

const titleInput=document.getElementById("mailDeskArticleTitleInput");
const suggestions=document.getElementById("mailDeskArticleTitleSuggested");
const journalInput=document.getElementById("mailDeskArticleJournal");
const searchButton=document.getElementById("mailDeskArticleTitleSearch");
const copyButton=document.getElementById("mailDeskArticleTitleCopy");
const manualStatus=document.getElementById("mailDeskArticleManualStatus");
if(!titleInput||!suggestions||!journalInput||!searchButton||!copyButton||!manualStatus)return;
style.textContent += ".brain-article-manual{padding:15px;margin-top:12px;background:#f8fbfc;border:1px solid #dce9ef;border-radius:10px}.brain-article-manual textarea{display:block;width:100%;min-height:72px;max-height:155px;padding:10px;border:1px solid #c7d9e2;border-radius:8px;resize:vertical;font-size:13px;line-height:1.5}.brain-article-search-row{display:grid;grid-template-columns:minmax(0,1fr) minmax(180px,250px);gap:10px;margin-top:10px}.brain-article-search-row label{display:block;font-size:12px;font-weight:650}.brain-article-search-row select{display:block;width:100%;min-width:0;margin-top:4px;padding:9px;border:1px solid #c7d9e2;border-radius:8px;background:#fff}.brain-article-lookup-links{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.brain-article-lookup-links a{padding:7px 10px;border:1px solid #b9d6df;border-radius:7px;text-decoration:none;font-weight:650;font-size:12px}.brain-article-lookup-links a:hover{background:#e7f3f6}.brain-article-input-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.brain-article-input-actions button{max-width:100%}@media(max-width:650px){.brain-article-search-row{grid-template-columns:1fr}}";
function note(message){manualStatus.textContent=message;}
function normalizedTitle(value){
 return String(value||"").replace(/^(?:t[ií]tulo da pesquisa|poss[ií]vel t[ií]tulo|t[ií]tulo)\s*[:\-]\s*/i,"").replace(/\s+/g," ").trim().slice(0,250);
}
window.brainMailArticleUseTitle = value => {
 const title=normalizedTitle(value);
 if(!title)return;
 titleInput.value=title;
 note("Título carregado do anexo. Confira se está completo e clique em “Pesquisar pelo título”.");
 titleInput.focus();
};
window.brainMailArticleSuggestions = items => {
 const current=titleInput.value.trim(),selected=suggestions.value;
 suggestions.replaceChildren();
 const blank=document.createElement("option");blank.value="";blank.textContent="Escolha um título detectado";suggestions.append(blank);
 const seen=new Set();let count=0;
 for(const item of Array.isArray(items)?items:[]){
  const title=normalizedTitle(item?.title_candidate);
  if(!item?.extracted||title.length<12||seen.has(title.toLowerCase()))continue;
  seen.add(title.toLowerCase());
  const option=document.createElement("option");option.value=title;
  option.textContent=(title.length>110?title.slice(0,107)+"…":title)+(item.filename?" · "+String(item.filename).slice(0,45):"");
  suggestions.append(option);count++;if(count>=25)break;
 }
 if(selected&&[...suggestions.options].some(x=>x.value===selected))suggestions.value=selected;
 if(!current && count===1){
  // A single attachment title is proposed but never silently treated as confirmed.
  titleInput.placeholder="Selecione o título sugerido ou escreva o título completo";
 }else{
  titleInput.placeholder="Cole ou digite o título completo do artigo (pode corrigir o texto extraído do anexo)";
 }
 if(count && !current)note(count+" título(s) detectado(s) nos anexos. Escolha o correto ou digite outro título para pesquisar.");
 else if(!count && !current)note("Não há título aproveitável nos anexos analisados. Insira o título do artigo para consultar as revistas.");
};
suggestions.addEventListener("change",()=>{if(suggestions.value)window.brainMailArticleUseTitle(suggestions.value)});
async function copyTitle(){
 const title=titleInput.value.trim();
 if(!title){note("Digite ou selecione um título antes de copiar.");return;}
 try{
  if(!navigator.clipboard?.writeText)throw Error("clipboard_unavailable");
  await navigator.clipboard.writeText(title);note("Título copiado. Cole-o na página da revista.");
 }catch{
  titleInput.focus();titleInput.select();note("Selecione o texto e use Ctrl+C para copiar o título.");
 }
}
copyButton.addEventListener("click",()=>{void copyTitle()});
document.querySelectorAll("[data-brain-journal-consultation]").forEach(anchor=>{
 anchor.addEventListener("click",()=>{
  const title=titleInput.value.trim();
  if(title&&navigator.clipboard?.writeText)navigator.clipboard.writeText(title).catch(()=>{});
  note(title?"Página de consulta aberta. Cole o título no campo de busca do periódico (Ctrl+V).":"Página de consulta aberta. Informe o título na busca do periódico.");
 });
});
async function resolve(threadId,cached=[],force=false,titleOverride="",journalOverride=""){
 const manual=Boolean(titleOverride);
 if(!threadId||busy.has(threadId)||(!manual&&!force&&checked.has(threadId))){
  if(busy.has(threadId)&&manual)note("Outra consulta está em andamento. Tente pesquisar novamente após a conclusão.");
  return;
 }
 if(!manual)checked.add(threadId);
 busy.add(threadId);refresh.disabled=true;searchButton.disabled=true;
 if(!manual)render(cached,"Consultando possíveis vínculos pelo histórico do e-mail…");
 else note("Pesquisando título no catálogo e nas APIs OJS autorizadas…");
 try {
  const payload={thread_id:threadId};
  if(manual){payload.title_override=titleOverride;payload.journal_override=journalOverride;}
  const result=await mailDeskCall("article_resolve",payload);
  if(typeof MAILDESK==="undefined"||MAILDESK.selected!==threadId)return;
  const matches=Array.isArray(result.matches)?result.matches:[];
  const rows=merge(cached,matches);
  if(MAILDESK.currentThreadData)MAILDESK.currentThreadData.article_identifications=rows;
  const failed=(result.lookups_attempted||[]).filter(x=>x.state!=="ok");
  let message="";
  if(result.matching_status==="review")message="Possíveis correspondências encontradas; confirme título e ID no OJS antes de vincular.";
  else if(!matches.length && manual)message="A pesquisa desse título não retornou uma correspondência confirmada. Verifique a grafia e consulte os links oficiais acima.";
  else if(!rows.length)message="Nenhuma correspondência confirmada apenas pelo histórico. Use um dos títulos extraídos do anexo acima.";
  else if(failed.length)message="Algumas consultas ao OJS ficaram indisponíveis; os resultados exibidos podem estar incompletos.";
  render(rows,message,message?"warning":"info");
  if(manual)note(matches.length?
    matches.length+" correspondência(s) encontrada(s) para o título informado. Confira o periódico antes de associar ao autor.":
    "Nenhum resultado confirmado para esse título. Você pode copiar o título e consultar diretamente a REMUNOM, RJNM ou RSV.");
 } catch(error){
  if(typeof MAILDESK!=="undefined"&&MAILDESK.selected!==threadId)return;
  render(cached,"A pesquisa editorial não foi concluída. Os títulos já extraídos dos anexos continuam disponíveis.","warning");
  if(manual)note("Não foi possível consultar o OJS agora. Copie o título e use os links das revistas.");
 } finally {
  busy.delete(threadId);
  if(typeof MAILDESK!=="undefined"&&MAILDESK.selected===threadId){
   refresh.disabled=false;searchButton.disabled=false;
  }
 }
}
window.brainMailArticleOpen=(threadId,data)=>{
 const cached=Array.isArray(data?.article_identifications)?data.article_identifications:[];
 refresh.disabled=false;searchButton.disabled=false;
 render(cached,cached.length?"":"Buscando correspondências pelo histórico. A identificação por anexos aparece acima.");
 if(!cached.length)void resolve(threadId,cached,false);
};
window.brainMailArticleClear=()=>{
 refresh.disabled=true;searchButton.disabled=true;
 titleInput.value="";journalInput.value="";suggestions.replaceChildren();
 const option=document.createElement("option");option.value="";option.textContent="Escolha um título detectado";suggestions.append(option);
 note("Selecione um título extraído dos anexos ou insira manualmente.");
 render([],"Aguardando a conversa…");
};
searchButton.addEventListener("click",()=>{
 if(typeof MAILDESK==="undefined"||!MAILDESK.selected){note("Selecione uma conversa primeiro.");return;}
 const title=normalizedTitle(titleInput.value);
 if(title.length<12){note("Informe ao menos 12 caracteres do título do artigo.");titleInput.focus();return;}
 titleInput.value=title;
 const cached=MAILDESK.currentThreadData?.article_identifications||[];
 void resolve(MAILDESK.selected,cached,true,title,journalInput.value);
});
refresh.addEventListener("click",()=>{
 if(typeof MAILDESK==="undefined"||!MAILDESK.selected)return;
 const cached=MAILDESK.currentThreadData?.article_identifications||[];
 void resolve(MAILDESK.selected,cached,true);
});
})();
