# Brain UJN — Expansão editorial e dashboards (11/11/2026)

## Entregas aplicadas

### 1. Fluxo editorial das cinco revistas
- Fontes `ujn_editorial_email_sources`: REMUNOM, RJNM, RSV, JIRRS e NEXUS `enabled=true`.
- OJS autenticados/read-only: verificados previamente nas cinco revistas.
- Rotinas existentes ativas: `ujn-editorial-wa-poll` de 15 em 15 minutos; `ujn_editorial_wa_approve_verified` e `ujn-editorial-wa-dispatch` a cada 5 minutos.
- Primeiro ciclo real comprovado: Pedro, REMUNOM, submissão 8379, template `ujn_editorial_update_ptbr`, aceito pela Meta; usuário confirmou o recebimento.
- A partir desta etapa, novas notificações das outras revistas **somente** serão enviadas a autores com vínculo de submissão e consentimento verificado. As outras quatro revistas estão habilitadas, mas ainda sem destinatários autorizados. NÃO cadastrar telefones ou consentimentos presumidos.

### 2. Dashboard de mensagens e relacionamento
No Brain UJN (GitHub Pages), duas novas páginas de navegação:
- `WhatsApp · Marketing`: destinatários verificados, mensagens aceitas, filas, falhas, alertas por revista, destinatários mascarados, sinais de interação posterior ao envio, estatísticas de leitura quando o webhook fornecer recibos.
- `IA · Atendimento`: conversas e mensagens, classificação de solicitações, relatório do histórico IMAP, base de conhecimento editável por aprovação e rascunhos de respostas supervisionados.

Backend de WhatsApp: `ujn-brain-marketing-insights` no projeto `leytqsyfrmzhectatcqm`. Backend de IA: `ujn-brain-ai-insights` no projeto `jufnkfyvqgkrxsbctqqk`. Ambos exigem login Academy e usuário superadministrador; origem permitida `https://peas8810.github.io`.

Status Meta: função `ujn-editorial-wa-receipt`, integrada ao webhook autenticado `ujn-whatsapp`, para capturar eventos futuros `delivered`, `read` e `failed`. Registrados novos campos `delivered_at`, `read_at`, `provider_status_at` na tabela `ujn_editorial_wa_deliveries`. **Não retropreencher** recibos de mensagens anteriores à implantação. `SENT` significa aceite da Meta, não prova de entrega. Os indicadores de interação são somente indícios de retorno no canal após o aviso, não prova de causalidade.

Marketing segregado: `ujn_marketing_permissions` no projeto da Central UJN, com opt-in comercial, origem, evidência e opt-out separados do consentimento editorial. Atualmente nenhum consentimento de marketing está registrado; disparos promocionais não foram implementados.

### 3. IA supervisionada
- Dados existentes: nove conversas WhatsApp / 211 mensagens, cinco entradas da base de conhecimento ainda em `DRAFT`, histórico IMAP de 16.497 recebidos + 5.771 enviados, amostra de 750+750 examinada sem exportação de corpos.
- Respostas do bot anterior NÃO são automaticamente políticas aprovadas.
- Botões de revisão da base de conhecimento acessíveis ao superadministrador.
- `suggest_reply` gera **rascunhos**, nunca envia. Se `OPENAI_API_KEY` estiver disponível no backend Academy, usa Responses API com `store:false` e texto reduzido/mascarado; caso contrário aplica apenas triagem por regras, claramente sinalizada como tal.
- A análise de e-mails completos ainda depende de ingestão segura do conteúdo da caixa institucional; no painel há campo de análise manual de e-mail. O diagnóstico existente contém apenas assuntos e metadados.
- Não foram importados e-mails pessoais ou inseridos dados sensíveis em repositórios públicos.

## Navegação
- Portal: `https://peas8810.github.io/teste_ujn/brain/`
- Arquivo fonte: `brain/index.html`
- Após abrir, login do operador Academy (superadministrador), recarregar página se necessário.

## Verificações
- As duas novas Edge Functions recusaram requisições sem autenticação com HTTP 403 `superadmin_required`.
- A conta de operador previamente usada possui `ujn_super=true`.
- Novas funções e alterações do webhook com deploys `ACTIVE`; o fluxo completo das novas telas deve ser validado no navegador com sessão de superadministrador — não foi possível simular sessão real a partir das ferramentas administrativas.

## Próximos passos para homologação completa
1. Acessar as duas telas pela sessão Academy, testar carregamento e registrar eventual erro de console.
2. Capturar um recibo de status Meta de nova mensagem para confirmar `delivered_at`/`read_at`.
3. Cadastrar pelo menos um autor autenticado e consentido para cada outra revista (JIRRS, NEXUS, RJNM, RSV).
4. Validar e aprovar respostas institucionais antes de habilitar a IA generativa; configurar a chave do provedor no ambiente seguro do backend, sem colá-la em chats.
5. Criar fluxo explícito de opt-in de marketing com prova, segmentação, revogação e limites de disparo antes de lançar campanhas.
6. Ampliar análise histórica das mensagens recebidas/enviadas no Webmail com filtragem de dados pessoais e revisão humana.
