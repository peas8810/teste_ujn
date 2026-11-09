# Brain UJN — Contrato de integração para a interface Manus
Data: 2026-11-09
Status: especificação técnica para integração; não significa que o frontend Manus esteja conectado.

## 1. Padrão visual oficial
Fonte do usuário: Manus (client/src/index.css, client/src/components/brain/Shell.tsx, client/src/components/brain/Primitives.tsx).
- Fundo: #f7f8fa; texto: #132b39; teal: #087e8b; borda: #e3e8ed; raio: 12px.
- Sidebar: #142c3b (222px desktop); hover #1d394a; ativo #254452; acento #43b2b6.
- Topbar branca 74px sticky; corpo 14px, entrelinha 1.55, H1 30px/H2 19px/H3 16px.
- Fontes: Inter corpo e Manrope títulos; contraste e foco visível 3px #28a5b8.
- Mobile <=820px: sidebar gaveta 240px; topbar 62px; Inbox lista e conversa em telas distintas.
- Não reproduzir o painel antigo GitHub Pages como base visual. Reaproveitar funcionalidades e contratos, não a aparência.

## 2. Regras de implantação
- A prévia Manus está explicitamente em modo DEMO: contatos sintéticos, sem contas reais e sem sincronização.
- Não exibir dados de produção sem login e autorização. Nunca conectar o navegador diretamente com service_role ou Meta token.
- Não alterar callback da Meta, credenciais, pagamentos ou certificados sem autorização expressa.
- Backend de atendimento: Supabase Academy, projeto jufnkfyvqgkrxsbctqqk.
- LAB de consulta editorial: projeto leytqsyfrmzhectatcqm.
- Aplicação Academy: https://www.protocolo.me/academy/
- Submissão externa: https://www.articlerun.org/submeter
- ArticleGenius: https://www.articlegenius.org/

## 3. Autenticação
Usar login Supabase Auth existente do Academy. Endpoint central:
POST https://jufnkfyvqgkrxsbctqqk.supabase.co/functions/v1/ujn-central
Headers: Authorization: Bearer <JWT do usuário>, apikey: <publishable Academy>, Content-Type: application/json.
Este endpoint valida o usuário e diferencia superadministrador, operador por serviço e titular.
O frontend Manus precisa de domínio de produção aprovado no CORS. NÃO fazer CORS aberto a qualquer Origin.
O login Google apresenta erro de provedor desabilitado até a configuração OAuth ser realizada no painel Supabase.

## 4. API da Central (ações existentes)
- { "action":"bootstrap" } -> services, allowed, superuser, user_id.
- { "action":"list","operator":true } -> conversas permitidas ao operador, até 200; operator:false -> conversas do próprio titular.
- { "action":"detail","id":"uuid" } -> histórico, anexos, estados de entrega; NOTE é restrita ao operador.
- { "action":"operator","id":"uuid","event_id":"uuid","operation":"...","revision":number,"text":"..." } -> ações do operador, conforme validações do servidor. Consultar enum do backend antes de implementar interface mutável.
- { "action":"file","id":"uuid" } -> URL temporária de arquivo com controle de acesso.
- { "action":"retry","id":"uuid" } -> reenvio condicionado às permissões e à janela WhatsApp.
- { "action":"menu_get" }, { "action":"menu_save","body":"...","version":number } -> edição do menu, apenas superadmin.
- { "action":"flow_get" }, { "action":"flow_save","service":"revistas|academy|escrita|articlerun|suporte","welcome":"...","knowledge":"...","questions":[],"version":number } -> textos por serviço, apenas superadmin.
- { "action":"academy_audit" } -> métricas agregadas Academy; { "action":"provider_health" } -> presença de configurações, sem retornar segredos.
- { "action":"operations_health" } -> agregados de fila WhatsApp, e-mail, notificações e conversas.
- { "action":"settings" } -> dados de configurações; antes de usar no frontend, RESTRINGIR campos e retirar quaisquer credenciais; não exibir esse retorno bruto.
- { "action":"link" } / { "action":"unlink" } -> fluxo de vínculo de WhatsApp por código temporário.

## 5. Menu de atendimento atual no backend
1 revistas -> acompanhamento OJS, declarações, normas.
2 academy -> pedidos, documentos, certificados (operações financeiras ainda bloqueadas).
3 escrita -> apenas https://www.articlegenius.org/
4 articlerun -> apenas https://www.articlerun.org/submeter
5 suporte -> informações e humano.
Comandos MENU/oi/voltar abrem o menu geral; seleção de revista oferece STATUS/DECLARAÇÃO/SUBMETER/NORMAS.
Busca por nome/ID no WhatsApp só pode exibir artigos PUBLICADOS, não dados editoriais de manuscritos privados.

## 6. Estado real e lacunas
- Canal WhatsApp Cloud API em uso; não redirecionar webhooks para o LAB.
- OJS: cinco credenciais de leitura verificadas no LAB. Busca pública por nome em OJS não está homologada em todas as revistas (inclusive limitações HTTP 429); não prometer completude.
- Acompanhamento privado: solicitação de vínculo pela conta Academy, homologação humana e consulta ao OJS; nenhum autor real vinculado na última checagem.
- Academy: 4 solicitações e 1 documento no momento da auditoria inicial; pagamentos, emissão e mensagens comerciais sem homologação; commercial_ready()=false em 2026-11-09.
- Portal Manus na captura é 100% DEMO. Nenhuma sincronização real foi confirmada.
- Necessário conectar Inbox por API, contatos por vínculo verificado, OJS por identificador autorizado e Academy por backend existente. Verificar desempenho, CORS, RLS, trilha de auditoria e papel do operador.

## 7. Ordem de implementação Manus
1. Conectar Auth e bootstrap; preservar distinção DEMO/PRODUÇÃO.
2. Implementar Inbox read-only: list, detail, entregas, paginação e busca; depois ativar operações humanas com revisão.
3. Contatos e vínculos: mostrar apenas identidade comprovada; número/nome isolado não comprova autoria.
4. Revistas: links, consulta pública, estado do artigo pelo OJS vinculado; não revelar revisão privada de terceiros.
5. Academy: solicitações e documentos, workflow de aprovação; somente depois sandbox MP, emissão, QR, revogação e envio.
6. Monitor notificações por canal e trilha de entregas, sem disparar mensagens até homologação.
7. Testes integrados com usuário e operador fictícios; só então considerar produção.

## 8. Repositórios acessíveis
- https://github.com/peas8810/teste_ujn (frontend legado e documentação; NÃO é o código React Manus mostrado na captura).
- https://github.com/peas8810/academy (outro repositório, não confundir com frontend Manus).
Para importar a interface Manus, disponibilizar o código client/src/* no GitHub conectado ou conector compatível.
