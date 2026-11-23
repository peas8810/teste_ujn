/* Brain UJN — bot de consulta pública por título ou autor.
   Mantém a leitura dos anexos e usa apenas a sessão autenticada do painel. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const root=$("mailDeskArticleIdentity"),refresh=$("mailDeskArticleIdentityRefresh"),
 input=$("mailDeskArticleTitleInput"),suggestions=$("mailDeskArticleTitleSuggested"),
 journal=$("mailDeskArticleJournal"),mode=$("mailDeskArticleMode"),
 search=$("mailDeskArticleTitleSearch"),copy=$("mailDeskArticleTitleCopy"),
 status=$("mailDeskArticleManualStatus");
if(!root||!refresh||!input||!suggestions||!journal||!mode||!search||!copy||!status)return;
const SITES={REMUNOM:"https://remunom.ojsbr.com/multidisciplinar/declaracoes/consulta",RJNM:"https://jrnm.ojsbr.com/juridica/declaracoes/consulta",RSV:"https://rsv.ojsbr.com/rsv/declaracoes/consulta"};
const allowed=new Set(["remunom.ojsbr.com","jrnm.ojsbr.com","rsv.ojsbr.com","doi.org","www.doi.org"]);
const running=new Set(),autoRan=new Set(),counts={};
const style=document.createElement("style");
style.textContent=".brain-article-manual{padding:15px;margin-top:12px;background:#f8fbfc;border:1px solid #dce9ef;border-radius:10px}.brain-article-manual textarea{display:block;width:100%;min-height:72px;max-height:155px;padding:10px;border:1px solid #c7d9e2;border-radius:8px;resize:vertical;font-size:13px;line-height:1.5}.brain-article-search-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:10px}.brain-article-search-row label{display:block;font-size:12px;font-weight:650}.brain-article-search-row select{display:block;width:100%;min-width:0;margin-top:4px;padding:9px;border:1px solid #c7d9e2;border-radius:8px;background:#fff}.brain-article-lookup-links{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.brain-article-lookup-links a{padding:7px 10px;border:1px solid #b9d6df;border-radius:7px;text-decoration:none;font-weight:650;font-size:12px}.brain-article-lookup-links a:hover{background:#e7f3f6}.brain-article-input-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.brain-article-list{display:grid;gap:12px;margin-top:12px}.brain-article-card{padding:15px;border:1px solid #d5e3e9;border-left:3px solid #078692;border-radius:10px;background:#fbfdfe}.brain-article-title{display:block;margin:6px 0 9px;font-size:14px;line-height:1.45;color:#183c50}.brain-article-meta{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12px;color:#496477}.brain-article-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:11px}.brain-article-actions a{display:inline-flex;padding:7px 10px;border-radius:7px;border:1px solid #b5d5df;font-size:12px;font-weight:650;color:#086e80;text-decoration:none}.brain-article-actions a:hover{background:#e8f5f7}.brain-article-actions button{font-size:12px}.brain-article-note{margin:8px 0 0;font-size:12px;color:#637584}.brain-article-muted{color:#637584;font-size:13px;margin:5px 0}.brain-article-status{display:inline-block;margin-left:9px;font-size:11px;font-weight:650;padding:3px 7px;border-radius:6px;background:#e4f2ef;color:#176a59}.brain-article-status.review{background:#fff4df;color:#885e18}@media(max-width:720px){.brain-article-search-row{grid-template-columns:1fr}}";
document.head.append(style);
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined&&text!==null)n.textContent=String(text);if(cls)n.className=cls;return n};
const note=text=>{status.textContent=text};
function safeUrl(value){
 try{const u=new URL(String(value||""));return u.protocol==="https:"&&!u.username&&!u.password&&allowed.has(u.hostname.toLowerCase())?u.href:null}
 catch{return null}
}
function link(parent,label,url){
 const good=safeUrl(url);if(!good)return;
 const a=el("a",label);a.href=good;a.target="_blank";a.rel="noopener noreferrer";a.referrerPolicy="no-referrer";parent.append(a);
}
function normalize(value){
 return String(value||"").replace(/^(?:t[ií]tulo da pesquisa|poss[ií]vel t[ií]tulo|t[ií]tulo)\s*[:\-]\s*/i,"").replace(/\s+/g," ").trim().slice(0,250)
}
function mergeItems(items){
 const out=new Map();
 for(const item of Array.isArray(items)?items:[]){
  if(!item?.journal_code||!item.submission_id)continue;
  const k=item.journal_code+":"+item.submission_id;
  const previous=out.get(k);
  if(!previous)out.set(k,item);
  else out.set(k,{...previous,...item,links:(item.links?.length?item.links:previous.links)||[]});
 }
 return [...out.values()].slice(0,100)
}
function render(items=[],checks=[],message=""){
 root.replaceChildren();
 if(message)root.append(el("p",message,"brain-article-muted"));
 if(Array.isArray(checks)&&checks.length){
  const summary=checks.map(x=>x.journal+": "+(x.status==="ok"?
   (x.found_count===null||x.found_count===undefined?"consulta concluída":x.found_count+" resultado(s)"):
   "consulta indisponível ("+x.status+")")).join(" · ");
  root.append(el("p",summary,"brain-article-note"));
 }
 const rows=mergeItems(items);
 if(!rows.length){if(!message)root.append(el("p","Nenhum resultado exibido. Selecione um título extraído do anexo ou pesquise pelo autor.","brain-article-muted"));return}
 const wrap=el("div",null,"brain-article-list");
 for(const item of rows){
  const card=el("article",null,"brain-article-card"),head=el("div");
  head.append(el("strong",item.journal_code+" · ID "+item.submission_id));
  const found=item.match_source==="consulta_publica";
  head.append(el("span",found?"Encontrado na página da revista":"Identificação preliminar","brain-article-status"+(found?"":" review")));
  card.append(head);
  card.append(el("strong",item.title||item.article_title||"Título não disponível","brain-article-title"));
  const info=el("div",null,"brain-article-meta");
  if(item.authors)info.append(el("span","Autores: "+item.authors));
  if(item.doi)info.append(el("span","DOI: "+item.doi));
  if(item.submission_date)info.append(el("span","Submetido em: "+item.submission_date));
  if(item.editorial_status==="published")info.append(el("span","Consta como publicado"));
  card.append(info);
  const actions=el("div",null,"brain-article-actions"),used=new Set();
  for(const l of item.links||[]){
   if(!safeUrl(l.url)||used.has(l.url))continue;used.add(l.url);link(actions,l.label||"Abrir documento",l.url)
  }
  for(const [label,url] of [["Artigo",item.article_url],["DOI",item.doi_url],["Página de consulta",item.consultation_url]]){
   if(!url||used.has(url))continue;used.add(url);link(actions,label,url)
  }
  const all=[...used].filter(u=>safeUrl(u));
  if(all.length){
   const button=el("button","Copiar links ("+all.length+")","btn small");button.type="button";
   button.onclick=async()=>{try{await navigator.clipboard.writeText(all.join("\n"));note("Links do artigo copiados para a área de transferência.");}
    catch{note("Não foi possível copiar automaticamente. Abra os links individualmente.")}};
   actions.append(button);
  }
  if(found){
   const add=el("button","Vincular ao e-mail","btn small");add.type="button";
   add.onclick=async()=>{
    if(typeof MAILDESK==="undefined"||!MAILDESK.selected)return;
    if(!confirm("Associar "+item.journal_code+" #"+item.submission_id+" a este e-mail? Confirme a autoria antes de usar esse vínculo."))return;
    add.disabled=true;
    try{
     const result=await mailDeskCall("article_link_add",{thread_id:MAILDESK.selected,journal_code:item.journal_code,submission_id:Number(item.submission_id)});
     if(typeof mailDeskDrawArticleLinks==="function")mailDeskDrawArticleLinks(result.article_links||[]);
     note("Vínculo administrativo registrado; não substitui conferência de autoria no OJS.");
    }catch(e){note("Não foi possível vincular: "+(e?.message||"erro de comunicação"))}
    finally{add.disabled=false}
   };
   actions.append(add)
  }
  card.append(actions);
  card.append(el("p","Links obtidos da página de consulta da revista. A identificação não comprova que o remetente é autor do artigo.","brain-article-note"));
  wrap.append(card)
 }
 root.append(wrap)
}
function updateDirectLinks(){
 for(const a of document.querySelectorAll("[data-brain-journal-consultation]")){
  const code=Object.keys(SITES).find(x=>a.href.startsWith(SITES[x]))||Object.keys(SITES).find(x=>a.textContent.includes(x));
  if(!code)continue;
  const url=new URL(SITES[code]),value=normalize(input.value);
  if(value){url.searchParams.set("query",value);url.searchParams.set("tipo",mode.value)}
  a.href=url.toString();
  a.title=value?"Abrir a busca na revista já preenchida por "+(mode.value==="autor"?"autor":"título"):"Abrir a consulta da revista";
 }
}
async function searchBot(raw,kind,selected,opts={}){
 const id=typeof MAILDESK==="undefined"?null:MAILDESK.selected;
 if(!id){note("Abra uma conversa para utilizar o bot.");return}
 const query=normalize(raw),force=opts.force===true;
 if(query.length<3){note("Informe um título ou nome do autor.");input.focus();return}
 if(running.has(id)){note("A consulta desta conversa já está em andamento.");return}
 running.add(id);search.disabled=true;refresh.disabled=true;const original=search.textContent;search.textContent="Consultando revistas…";
 if(!opts.silent){note("O bot está consultando o formulário público das revistas por "+(kind==="autor"?"autor":"título")+"…");render([],[],"Pesquisando nas páginas de consulta…")}
 try{
  const result=await mailDeskCall("article_consulta_bot",{thread_id:id,query,tipo:kind,journal:selected||"ALL",force});
  if(typeof MAILDESK==="undefined"||MAILDESK.selected!==id)return;
  const items=Array.isArray(result.items)?result.items:[],checks=result.journals_checked||[];
  const unavailable=checks.some(x=>x.status!=="ok");
  let message=items.length?
   items.length+" registro(s) encontrado(s) nas páginas públicas. Os links aparecem abaixo.":
   unavailable?"Não foi possível concluir a pesquisa em todas as revistas. Confira os avisos abaixo.":
   "Nenhum registro encontrado para essa pesquisa. Confira o título ou tente o nome do autor.";
  if(items.length&&unavailable)message+=" Algumas revistas ficaram indisponíveis.";
  render(items,checks,message);
  note((result.from_cache?"Resultado salvo · ":"")+"Pesquisa concluída. "+items.length+" registro(s) encontrado(s).");
  if(MAILDESK.currentThreadData)MAILDESK.currentThreadData.consulta_cache={
   query_text:query,search_mode:kind,journal:selected||"ALL",results:items,journal_checks:checks,
   complete:result.complete===true,updated_at:new Date().toISOString()
  }
 }catch(e){
  if(typeof MAILDESK!=="undefined"&&MAILDESK.selected!==id)return;
  render([],[],"A consulta direta não pôde ser concluída. Tente novamente ou abra o link oficial da revista.");
  note("Falha na consulta: "+(e?.message||"serviço indisponível"))
 }finally{
  running.delete(id);
  if(typeof MAILDESK!=="undefined"&&MAILDESK.selected===id){search.disabled=false;refresh.disabled=false;search.textContent=original;}
 }
}
window.brainMailArticleOpen=(id,data)=>{
 search.disabled=false;refresh.disabled=false;
 const cache=data?.consulta_cache;
 if(cache?.query_text){
  input.value=cache.query_text;mode.value=cache.search_mode||"titulo";journal.value=cache.journal==="ALL"?"":cache.journal;
  render(cache.results||[],cache.journal_checks||[],cache.results?.length?"Resultado da última consulta salvo na conversa.":"Última consulta sem correspondências.");
  note("Última pesquisa: "+cache.query_text);
 }else{
  const old=data?.article_identifications||[];
  render(old,[],old.length?"Artigo anteriormente identificado. A pesquisa pela página pública pode retornar mais links.":"O bot usará o título extraído do anexo. Você também pode digitar título ou autor.");
  note("Aguardando análise dos anexos ou pesquisa manual.");
 }
 updateDirectLinks()
};
window.brainMailArticleClear=()=>{
 search.disabled=true;refresh.disabled=true;
 input.value="";mode.value="titulo";journal.value="";
 suggestions.replaceChildren(el("option","Escolha um título detectado"));
 render([],[],"Selecione um e-mail para consultar artigos.");
 note("Aguardando conversa.");
 updateDirectLinks()
};
window.brainMailArticleUseTitle=value=>{
 const title=normalize(value);if(!title)return;
 mode.value="titulo";input.value=title;updateDirectLinks();
 note("Título recebido do anexo. Consultando nas páginas da revista…");
 void searchBot(title,"titulo",journal.value||"ALL")
};
window.brainMailArticleSuggestions=items=>{
 const selected=suggestions.value,current=input.value.trim();
 suggestions.replaceChildren();
 const blank=el("option","Escolha um título detectado");blank.value="";suggestions.append(blank);
 const valid=[],seen=new Set();
 for(const item of Array.isArray(items)?items:[]){
  const title=normalize(item?.title_candidate),filename=String(item?.filename||"");
  if(!item?.extracted||title.length<12||seen.has(title.toLowerCase()))continue;
  seen.add(title.toLowerCase());valid.push({title,filename});
  const o=el("option",(title.length>100?title.slice(0,97)+"…":title)+(filename?" · "+filename.slice(0,38):""));
  o.value=title;suggestions.append(o)
 }
 if(selected&&[...suggestions.options].some(x=>x.value===selected))suggestions.value=selected;
 if(!current&&valid.length)note(valid.length+" título(s) encontrado(s) nos anexos. O bot dará preferência ao manuscrito Word.");
 const threadId=typeof MAILDESK==="undefined"?null:MAILDESK.selected;
 const cache=MAILDESK?.currentThreadData?.consulta_cache;
 if(!threadId||!valid.length||cache||autoRan.has(threadId)||running.has(threadId))return;
 const word=valid.filter(x=>/\.docx?$/i.test(x.filename)&&!/(parecer|pl[aá]gio|comprovante|resposta)/i.test(x.filename));
 const pick=word.length===1?word[0]:valid.length===1&&valid[0].title.length>=28?valid[0]:null;
 if(!pick){note("Há vários títulos nos anexos. Selecione o manuscrito correto para evitar associar artigos diferentes.");return}
 autoRan.add(threadId);
 mode.value="titulo";input.value=pick.title;updateDirectLinks();
 note("Título do manuscrito detectado. Iniciando consulta automática nas revistas…");
 void searchBot(pick.title,"titulo",journal.value||"ALL",{silent:false})
};
suggestions.onchange=()=>{if(suggestions.value)window.brainMailArticleUseTitle(suggestions.value)};
mode.onchange=()=>{
 const isAuthor=mode.value==="autor";
 input.placeholder=isAuthor?"Digite o nome completo do autor para pesquisar nas revistas":"Cole ou selecione o título completo do artigo";
 suggestions.disabled=isAuthor;
 updateDirectLinks()
};
input.addEventListener("input",updateDirectLinks);
journal.addEventListener("change",updateDirectLinks);
search.onclick=()=>void searchBot(input.value,mode.value,journal.value||"ALL",{force:true});
refresh.onclick=()=>void searchBot(input.value,mode.value,journal.value||"ALL",{force:true});
copy.onclick=async()=>{const value=input.value.trim();if(!value){note("Insira um título ou autor antes de copiar.");return}
 try{await navigator.clipboard.writeText(value);note("Texto copiado.");}
 catch{input.focus();input.select();note("Selecione o texto e pressione Ctrl+C para copiar.")}};
updateDirectLinks();
})();