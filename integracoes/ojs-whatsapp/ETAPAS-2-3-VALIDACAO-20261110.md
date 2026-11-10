# Brain UJN — Conclusão técnica dos itens 2 e 3 (10/11/2026)

## Item 2 — identificação do autor e telefone

Implantada a função administrativa `public.ujn_editorial_stage_author(p_journal_code,p_submission_id,p_author_email,p_phone_e164,p_recipient_role)`. Ela:
- recebe exatamente revista, ID de submissão, e-mail e telefone E.164, valida os formatos e calcula o SHA-256 do e-mail sem armazená-lo em texto na tabela de destinatários;
- cadastra em `public.ujn_editorial_wa_recipients` **sem** afirmar consentimento ou autoria verificada; em caso de atualização, restaura o estado não verificado;
- pode ser chamada apenas por `service_role`, sem autorização para `anon` ou `authenticated`;
- depende da conferência administrativa dos dados do autor junto ao OJS e da comprovação separada de consentimento, com origem, evidência e data antes de marcar `verified_at`.

**Não foram inseridos números ou consentimentos falsos.** No instante da auditoria, `verified_recipients=0`. O serviço de envio exige `verified_at`, `consent_at` e ausência de revogação.

## Item 3 — eventos e ingestão Supabase

Realizado teste de ponta a ponta **da assinatura HMAC até o classificador da Edge Function** `ujn-editorial-email-ingest`, em ação `dry_run`, para as cinco revistas:

| Revista | HTTP | Evento reconhecido | ID da submissão único |
|---|---|---|---|
| JIRRS | 200 | submission_received | sim |
| NEXUS | 200 | submission_received | sim |
| REMUNOM | 200 | submission_received | sim |
| RJNM | 200 | submission_received | sim |
| RSV | 200 | submission_received | sim |

Requisições Supabase pg_net IDs 689-693, respostas sem erro e `notifications_sent=0`. Os ID e domínios usados nesses cinco testes são **dados sintéticos** e não evidência de submissões reais.

Criada também a visão `public.ujn_editorial_readiness` de acompanhamento por revista com colunas: fonte de e-mail, estado de conector OJS, destinatários verificados, ingestões, eventos, envios preparados e envios aceitos. Acesso à visão restrito a `service_role`.

Consulta de auditoria:
```sql
select * from public.ujn_editorial_readiness order by journal_code;
```

Estado confirmado: cinco fontes de e-mail habilitadas e cinco conectores em `verified_readonly`; **0** autores verificados, **0** eventos de e-mails reais, **0** entregas.

## O que ainda depende de fatos do mundo real

- Capturar uma mensagem legítima de cada revista na caixa `contato@ujn.ojsbr.com` **endereçada ao autor**, ou confirmar eventos por API autenticada por submissão. O teste assinado ao endpoint não demonstra que o cPanel entregou e-mails reais.
- Obter telefone de autores reais e consentimento individual comprovável; o administrador da editora pode habilitar o serviço mas não substituir autorizações dos destinatários.
- Aguardar status da Meta `Ativo` para o modelo `ujn_editorial_update_ptbr`, realizar envio a um número de teste consentido e verificar recibo.
- Não expor links administrativos nem pareceres completos por WhatsApp.

A configuração geral `delivery_enabled=true` não significa que alguma mensagem foi enviada. A condição de autor verificado e mensagem `READY` continua obrigatória.
