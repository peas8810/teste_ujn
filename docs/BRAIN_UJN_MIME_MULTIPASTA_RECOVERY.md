# Brain UJN — Recuperação MIME multipastas (16/11/2026)

## Objetivo
Investigar mensagens importadas sem corpo: na auditoria mais recente, 104 mensagens INBOUND ainda tinham body_text e body_html vazios. Um teste na INBOX encontrou 1 de 10 candidatas e não localizou outras 9 nessa pasta.

## Entrega
Arquivo Python independente `integracoes/webmail/ujn_imap_multipasta_repair.py`, sem mudança nas quatro rotinas principais nem no sincronizador de flags Roundcube.

- Pesquisa o Message-ID exato nas pastas IMAP selecionáveis de recebimento: INBOX, Arquivo/Archive e pastas customizadas;
- Exclui por padrão `\\Trash`, `\\Junk`, `\\Sent`, `\\Drafts`, Spam, Lixeira, Enviados e Rascunhos;
- Faz `UID SEARCH HEADER Message-ID` e `BODY.PEEK[]`, verifica cabeçalho e remetente/destinatário da mensagem, sem modificar flags;
- Envia conteúdo apenas à Edge Function de ingestão já autenticada por HMAC e apenas para atualização de campos vazios, não modifica textos preenchidos;
- Só conta como `restored` quando o Supabase confirma `enriched:true`, distinguindo `already_present`, `original_empty`, `not_found`, `errors`, `deferred`;
- Tem checkpoint próprio em `/home/ujn/brain-ujn/state/mime_multipasta_repair_state.json` e usa o lock compartilhado com o coletor incremental;
- Não usa o checkpoint anterior `mime_body_repair_state.json` que marcara as 9 ausentes da INBOX como faltantes;
- Não envia e-mails, não copia credenciais, não altera pasta, não deleta nem faz `EXPUNGE`.

## Instalação sem Terminal
No cPanel do apolo.ojsbr.com, instalar `ujn_imap_multipasta_repair.py` em `/home/ujn/brain-ujn/` ao lado do leitor e coletor IMAP existentes.
Excluir qualquer **sexto Cron temporário** anterior de reparação que não esteja mais em uso; manter os cinco Cron permanentes.

### Teste de diagnóstico sem alteração de mensagens
Criar um sexto Cron temporário com os cinco campos `*`, comando:
```sh
if [ ! -f /home/ujn/brain-ujn/state/mime_multipasta_diagnose_once.flag ]; then /usr/bin/python3 -m py_compile /home/ujn/brain-ujn/ujn_imap_multipasta_repair.py && timeout 75s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_multipasta_repair.py --diagnose > /home/ujn/brain-ujn/state/mime_multipasta_diagnose.log 2>&1; if grep -q '"mime_multipasta": "DIAGNOSTIC"' /home/ujn/brain-ujn/state/mime_multipasta_diagnose.log; then touch /home/ujn/brain-ujn/state/mime_multipasta_diagnose_once.flag; fi; fi
```
Log esperado: `mime_multipasta:DIAGNOSTIC`, `folders_available`, `folder_names`, `no_changes:true` e `sent_email:false`.
Se houver `ALREADY_RUNNING`, o lock do coletor está em uso, e a tarefa tentará novamente sem interferir nele.

### Primeiro lote real, após diagnóstico aprovado
**Editar a sexta tarefa Cron temporária**, substituindo o comando por:
```sh
if [ ! -f /home/ujn/brain-ujn/state/mime_multipasta_batch_once.flag ]; then UJN_MIME_MULTIPASTA_BATCH=8 UJN_MIME_MULTIPASTA_SECONDS=65 timeout 90s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_multipasta_repair.py > /home/ujn/brain-ujn/state/mime_multipasta_batch.log 2>&1; if grep -q '"mime_multipasta": "COMPLETE"' /home/ujn/brain-ujn/state/mime_multipasta_batch.log; then touch /home/ujn/brain-ujn/state/mime_multipasta_batch_once.flag; fi; fi
```
- Não adicionar Cron adicional. A tarefa é um teste único com até 8 candidatas e retomada automática somente após lock ocupado.
- Verificar `state/mime_multipasta_batch.log`; `restored > 0` indica campo de conteúdo realmente preenchido no banco.
- Se mostrar `deferred > 0`, o tempo acabou antes de procurar todas as pastas: não ampliar o lote; será necessário repetir controladamente mantendo o checkpoint.
- Remover o sexto Cron temporário depois da verificação. Não apagar os arquivos de checkpoint nem criar vários Cron de reparação em paralelo.

## Homologação
1. Verificar no Supabase total de mensagens vazias antes/depois do teste;
2. Reabrir ao menos uma conversa recuperada;
3. Verificar que número de conversas e de mensagens não aumentou devido à recuperação;
4. Confirmar que Reply-To, Seen/Answered e SMTP permaneceram preservados;
5. Se o `Message-ID` não for encontrado nas pastas permitidas, não inventar conteúdo; possíveis origens: mensagem movida à Lixeira, removida do servidor, headers alterados, pasta não selecionável, originalmente vazia.

## Consulta SQL
```sql
select count(*) filter(where btrim(coalesce(body_text,''))='' and btrim(coalesce(body_html,''))='') as ainda_vazios,
 count(*) as recebidos from public.ujn_email_desk_messages where direction='INBOUND';
```
