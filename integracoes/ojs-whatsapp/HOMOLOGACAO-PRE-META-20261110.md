# Homologação pré-Meta — Brain UJN — 10/11/2026

## Implementações realizadas
- Criada função read-only `ujn-editorial-readiness-probe`, protegida por token interno, para verificar a leitura autenticada das listas de submissões nos cinco OJS. Não devolve nomes, títulos, e-mails, telefones, tokens ou textos privados.
- Criada a configuração `ujn_editorial_wa_settings.automatic_approval_enabled=true` e a função `public.ujn_editorial_wa_approve_verified(25)`.
- Configurado `pg_cron` job ID 4, `ujn_editorial_wa_approve_verified`, a cada 5 minutos para converter `PENDING_APPROVAL` em `READY` apenas se: revista e submissão correspondem, número E.164, autor verificável, consentimento e comprovante registrados, ausência de revogação, evento posterior ao consentimento e à verificação, data do evento nos últimos 3 dias, modelo correto `ujn_editorial_update_ptbr` e origem/evento permitidos.
- O despachante existente `ujn-editorial-wa-dispatch` já estava agendado a cada 5 minutos. A sondagem `ujn-editorial-wa-poll` já estava agendada a cada 15 minutos.
- Comando de cancelamento `PARAR` identificado no webhook `ujn-whatsapp`, ligado à função `ujn-editorial-wa-optout`.

## Testes executados — resultados conferidos
| Teste | Resultado |
|---|---|
| OJS REMUNOM: GET listagem de submissões com credencial configurada | HTTP 200, JSON válido, lista |
| OJS JIRRS: idem | HTTP 200, JSON válido, lista |
| OJS NEXUS: idem | HTTP 200, JSON válido, lista |
| OJS RSV: idem | HTTP 200, JSON válido, lista |
| OJS RJNM: idem | HTTP 200, JSON válido, lista |
| Supabase ingestão HMAC, `dry_run`, 5 revistas | 5 HTTP 200; submissão e evento sintéticos reconhecidos, zero envio |
| Ingestão sem assinatura | HTTP 401 `invalid_signature` |
| Despacho com autenticação interna | HTTP 200, `attempted=0,accepted=0,blocked=0` |
| Aprovação automática sem autor | `approved_now=0`; nenhum destinatário incorreto |
| Agendamento aprovação automática | Job 4 ativo `*/5 * * * *` |
| Comando PARAR no webhook | Encaminhamento detectado no código, execução com telefone real não testada |
| Respostas IMAP locais | último relatório enviado pelo usuário `status=OK`, `ingest_configured=true`, sem mensagens novas |
| Mensagens reais Meta | **Não enviadas** (template pendente; destinatários 0) |

Testes HTTP no Supabase: `pg_net` request 694 = API five read-only, 696 = assinatura inválida, 697 = dispatch com fila vazia. A sondagem de leitura autenticada de cinco OJS prova acesso à **listagem**, não prova leitura de todos os detalhes e transições de submissões.

## Pendências de produção que não são supridas pela aprovação do modelo Meta
1. **Autor, telefone, submissão, e-mail e prova de consentimento**: a tabela `ujn_editorial_wa_recipients` continua vazia. Usar fluxo de opt-in comprovável; não marcar em lote todos os autores como consentidos por decisão administrativa. O cadastro em duas etapas `ujn_editorial_stage_author` já existe.
2. **Eventos reais em cada revista**: os cinco testes validaram APIs e parser do backend, mas não o evento IMAP real da revista ao autor nem uma alteração de etapa de uma submissão consentida detectada pelo `ujn-editorial-wa-poll`.
3. **Template Meta**: o modelo `ujn_editorial_update_ptbr` está configurado no canal UJN, mas a última tela apresentada estava `Em análise`; não afirmar que foi aprovado sem verificar.
4. **Primeiro envio e recibo Meta**: testar em um telefone próprio com opt-in, comprovar ID de mensagem e status entregue. O dispatcher registra `SENT` após aceite da Meta, não comprova entrega sem recibo.
5. **Automação IMAP**: manter cron e a chave HMAC 600; o monitor só observa e-mails que chegam em `contato@ujn.ojsbr.com` e não garante cópias dos e-mails a todos os autores.

## Consultas administrativas
```sql
select * from public.ujn_editorial_readiness order by journal_code;
select polling_enabled,delivery_enabled,automatic_approval_enabled from public.ujn_editorial_wa_settings where id=true;
select jobid,jobname,schedule,active from cron.job where jobid in (2,3,4);
select state,count(*) from public.ujn_editorial_wa_deliveries group by state;
```

**Não foi gerado nenhum autor ou consentimento fictício, nem realizada chamada de envio de WhatsApp a terceiros.**