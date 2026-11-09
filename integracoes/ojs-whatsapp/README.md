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
