# Brain UJN — E-mails com corpo ausente

## Auditoria (16/11/2026)
No Supabase foram constatados, em 347 mensagens INBOUND, 105 registros com `body_text` e `body_html` vazios, e 32 com apenas HTML. Caso reproduzido: notificação com assunto `Re: Confirmação de Aceite e Procedimentos para Finalização Editorial`, recebida em 13/11/2026, com `Reply-To` do destinatário final e nenhum corpo no banco.

### Causas corrigidas
1. O leitor `ujn_imap_readonly_collector.py` só procurava `text/plain`; agora também extrai texto legível de HTML quando não houver texto puro, ignora partes anexadas e faz fallback para charsets inválidos.
2. O adaptador `ujn_email_mime_adapter.py` passa a ignorar charsets inválidos do HTML com fallback UTF-8, sem abortar a mensagem.
3. A Edge Function `ujn-email-desk-v1` **agora completa `body_text` e `body_html` de mensagens já existentes quando esses campos estão vazios**, sem substituir conteúdo não vazio e sem criar duplicatas. A reconciliação é feita pelo `Message-ID` original e HMAC do coletor.
4. A RPC privada `ujn_email_desk_missing_body_candidates` lista IDs exatos dos registros sem corpo para o coletor do servidor.
5. `ujn_imap_missing_body_repair.py` lê a mensagem original no IMAP INBOX via `UID SEARCH HEADER Message-ID`, valida a correspondência exata, usa `BODY.PEEK[]` e reenriquece via ingestão existente. Não envia, exclui, movimenta nem marca mensagens como lidas. Usa lock compartilhado com o incremental e checkpoint de chaves tentadas.

## Implantação no cPanel
Pasta privada: `/home/ujn/brain-ujn/`. Substituir:
- `ujn_imap_readonly_collector.py` (módulo usado pelo incremental e reparador)
- `ujn_email_mime_adapter.py` (atualizar extractor HTML)
Adicionar:
- `ujn_imap_missing_body_repair.py`

**Não modificar nenhum Cron permanente existente.** Validação via quinta tarefa temporária uma vez (campos `*`):
```sh
if [ ! -f /home/ujn/brain-ujn/state/mime_repair_diagnostic.flag ]; then touch /home/ujn/brain-ujn/state/mime_repair_diagnostic.flag; ( /usr/bin/python3 -m py_compile /home/ujn/brain-ujn/ujn_imap_readonly_collector.py /home/ujn/brain-ujn/ujn_email_mime_adapter.py /home/ujn/brain-ujn/ujn_imap_missing_body_repair.py && timeout 40s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_missing_body_repair.py --diagnose ) > /home/ujn/brain-ujn/state/mime_repair_diagnostic.log 2>&1; fi
```
Verificar `state/mime_repair_diagnostic.log` antes de qualquer reparação. Esperado: `mime_repair: DIAGNOSTIC`, `candidates_sample` e `no_changes: true`.

Após diagnóstico, editar apenas o Cron temporário para um teste controlado único de até 10 mensagens, com flag separada:
```sh
if [ ! -f /home/ujn/brain-ujn/state/mime_repair_once.flag ]; then touch /home/ujn/brain-ujn/state/mime_repair_once.flag; UJN_IMAP_MIME_ENABLED=1 UJN_IMAP_ATTACHMENTS_ENABLED=0 UJN_MIME_REPAIR_BATCH=10 timeout 80s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_missing_body_repair.py > /home/ujn/brain-ujn/state/mime_repair_once.log 2>&1; fi
```
A flag cria um limite de apenas uma tentativa para esse lote. Excluir a tarefa temporária após registrar o resultado. O reparador usa checkpoint `state/mime_body_repair_state.json`; mensagens ausentes da INBOX, ambíguas ou originalmente sem corpo não ganham texto inventado.

## Critérios de homologação
- Reabrir a notificação anteriormente vazia depois de reprocessada, conferir o texto real.
- Comparar quantidade de registros `body_text`/`body_html` vazios antes e depois.
- Validar que não surgiram mensagens duplicadas e que o `Reply-To` e flags `\Seen`/`\Answered` permaneceram intactos.
- Para conteúdos disponíveis apenas na pasta de Arquivo ou outra pasta IMAP, precisaríamos de recuperação pontual autorizada nessa pasta; a versão atual trabalha somente na INBOX.
- Mensagens sem texto também no original não são passíveis de recuperação por esse fluxo.

## Segurança
Os scripts usam credenciais já existentes no cPanel, fora do `public_html`. Não solicite senhas/tokens. Nenhum SMTP ou automação de envio é modificado.
