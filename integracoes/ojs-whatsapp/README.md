# Brain UJN — Notificações OJS → WhatsApp

**Status em 09/11/2026:** infraestrutura de coleta em homologação; envios externos **desativados** até confirmação de consentimento, templates aprovados pela Meta e instalação dos hooks OJS. Sistema independente do ACADEMY.

## Arquitetura

1. Cada revista (REMUNOM, JIRRS, NEXUS, RSV, RJNM) envia um evento editorial assinado à função `ujn-editorial-ojs-events`.
2. A função valida assinatura HMAC SHA-256 exclusiva da revista e impede o processamento repetido do mesmo identificador.
3. O evento é registrado no Supabase de homologação, associado ao código da revista e ID da submissão.
4. Destinatários precisam ter telefone `+E164`, prova de consentimento e identidade verificada. Apenas essas inscrições geram rascunhos de entrega.
5. Um envio definitivo exigirá modelo **Utility** aprovado na conta Meta da Editora UJN, checagem de revogação, idempotência, limite de frequência e confirmação do provedor.
6. E-mails OJS continuam independentes e não devem ser alterados.

## Evento de exemplo (sem dados confidenciais)

```json
{
  "event_id": "rjnm-submission-8267-copyediting-20261109T194000Z",
  "submission_id": 8267,
  "event_type": "copyediting_started",
  "occurred_at": "2026-11-09T19:40:00Z",
  "title": "Título do manuscrito",
  "doi": "10.66104/gdmjsm29"
}
```

A assinatura é `sha256=hex(HMAC_SHA256(secret, timestamp + "." + json_body))`. Headers: `x-ujn-journal`, `x-ujn-timestamp` (Unix segundos), `x-ujn-signature` e `Content-Type: application/json`. O relógio do servidor deve estar sincronizado, com tolerância de 5 minutos. Segredos diferentes para cada revista devem ser obtidos por um administrador autorizado e configurados no servidor do OJS, **nunca** no front-end.

## Integração ao OJS

O arquivo `EditorialWhatsAppRelay.php` é apenas o transporte HTTP seguro. A hospedagem de cada revista precisa instalar o módulo de hooks compatível com a versão exata do OJS e chamar `UjnEditorialWhatsAppRelay::deliver()` após o evento ter sido persistido. Não chamar no início da transação nem assumir que todas as mensagens internas são direcionadas ao autor.

Eventos aceitos: `submission_received`, `editor_assigned`, `review_started`, `review_round_created`, `review_requested`, `review_completed`, `revision_requested`, `revision_submitted`, `editor_message_available`, `author_message_available`, `editorial_decision`, `accepted`, `declined`, `copyediting_started`, `production_started`, `proof_requested`, `proof_approved`, `published`, `publication_updated`, `withdrawn`, `other_activity`.

**Nunca enviar ao WhatsApp:** texto de pareceres, identidade de avaliadores em revisão anônima, anexos confidenciais, dados privados de outros autores ou links internos de edição. Avisos de mensagem/parecer devem dizer apenas que há uma comunicação disponível para o autor consultar no OJS.

## Fallback por leitura OJS

A função `ujn-editorial-wa-poll` detecta mudanças amplas de estágio, situação, início de rodada e publicação, comparando snapshots dos artigos com assinantes elegíveis. A primeira leitura estabelece baseline e não deve gerar notificações retroativas. **Polling não garante capturar todas as movimentações**, especialmente várias mensagens entre verificações: para paridade com os e-mails o webhook de eventos OJS é necessário.

## Notificação genérica proposta para aprovação na Meta

Template sugerido: `ujn_editorial_update_ptbr`, categoria **UTILITY**, idioma `pt_BR`.

> Olá, {{1}}. A revista {{2}} registrou uma atualização na sua submissão {{3}}: {{4}}. Acesse o sistema editorial para consultar os detalhes. Para interromper os avisos por WhatsApp, responda PARAR.

É somente uma proposta de template. Não afirmar aprovação. Acesso a detalhes do processo editorial exige autenticação no OJS.

## Pendências antes de habilitar envio

- Confirmar campo de telefone e consentimento opt-in em cada OJS. Não presumir que cadastrar telefone = consentimento Meta.
- Vincular cada `journal_code + submission_id` ao telefone do autor correspondente mediante prova e validação.
- Instalar hooks/relay no servidor OJS das cinco revistas e homologar pelo menos um evento de cada tipo.
- Aprovar template no WhatsApp Manager e confirmar a conta da Meta responsável pelo número UJN.
- Construir despachante de produção com fila idempotente, limite de frequência, opt-out e retorno de status de entrega.
- Validar desativação/retomada e falhas antes de ligar `delivery_enabled`.


## Implementação executada — atualização 09/11/2026

Todos os cinco sites anunciaram **Open Journal Systems 3.5.0.5** no meta `generator`. Foi criada uma estrutura central compartilhada:
- `ujn-editorial-ojs-events`: eventos assinados HMAC e inscrição/cancelamento consentidos vindos dos servidores OJS
- `ujn-editorial-wa-poll`: consulta periódica de transições de estágio/status para inscrições verificadas
- `ujn-editorial-wa-dispatch`: fila de envios aprovados, revalidação de consentimento, concorrência e idempotência
- `ujn-editorial-template-gateway`: canal Meta da Editora UJN, envio **somente via template** `ujn_editorial_update_ptbr`
- `ujn-editorial-wa-optout`: cancelamento por telefone; mensagem PARAR interceptada no WhatsApp UJN

### OJS 3.5 — arquivos preparados, ainda não instalados nos servidores

O diretório `plugin-ojs35/` contém um plugin genérico para a versão 3.5.0.5. É uma **primeira versão**, que cobre:
- `Submission::add` → evento `submission_received`
- `Decision::add` → evento `editorial_decision`

Esses dois hooks são compatíveis com os nomes documentados do OJS. Entretanto, instalar arquivos no GitHub **não os instala nos cinco OJS**. É necessário acesso ao servidor/gerenciador de plugins e testes de compatibilidade em homologação. E-mails OJS não são alterados.

**Ainda não conectados ao plugin:** mensagens de discussão/pareceres, comentários do editor, pedidos de prova, prazos de revisão e eventos específicos de cada comunicação. Os eventos são aceitos na API, mas exigem hooks adicionais ou um mecanismo institucional no OJS que os emita após a gravação. Não confundir “evento aceito pela API” com “evento efetivamente detectado na revista”.

### Instalação pelo responsável técnico do OJS

1. Copiar os quatro arquivos de `plugin-ojs35/` para `plugins/generic/ujnEditorialWa/` em cada instalação OJS 3.5.0.5; verificar que o mecanismo de autoload do OJS encontra a classe.
2. Definir **no ambiente do servidor**, não em HTML nem GitHub: `UJN_OJS_WA_JOURNAL` = código exato da revista e `UJN_OJS_WA_SIGNING_KEY` = chave exclusiva do webhook. Obter a chave no cofre Supabase por método administrativo seguro, não registrá-la em logs.
3. Habilitar o plugin na administração do OJS, confirmar hooks e validar a criação de evento com uma submissão de teste.
4. Preparar o opt-in explícito dos autores no formulário institucional. A chamada assinada `subscription_opt_in` aceita `submission_id`, `phone_e164`, `recipient_role: corresponding_author`, `consent_at`, `consent_source: ojs_author_optin`, `consent_evidence_ref: ojs:...`. Não cadastrar destinatários apenas por possuírem telefone no perfil.
5. Registrar/revisar o template Utility `ujn_editorial_update_ptbr` em português do Brasil no WhatsApp Manager, e só configurar `ujn_channels.template_name` após aprovação real.
6. Realizar homologação com consentimento de uma conta de teste por revista; verificar duplicatas e o comando `PARAR`; somente então habilitar `delivery_enabled` no banco após aprovação administrativa.

### Estado do banco em 09/11/2026

`polling_enabled=true`; `delivery_enabled=false`. Fila do dispatcher ativa a cada 5 minutos, mas com envio bloqueado. A API editorial possui cinco chaves de webhook distintas. Não há assinantes cadastrados na fila nova. Não foram enviados WhatsApps automáticos editoriais.

**Atenção a produção:** o plugin é um ponto inicial para homologação e não substitui os testes de instalação no OJS. Não expõe identidades de pareceristas nem o conteúdo dos pareceres. Para entregar “cada movimentação”, ainda é necessária a conexão dos eventos de correspondência internos em todas as revistas.
