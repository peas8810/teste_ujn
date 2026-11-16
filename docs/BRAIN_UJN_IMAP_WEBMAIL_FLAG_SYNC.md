# Brain UJN → Roundcube: flags IMAP lida e respondida

## Resultado implantado no backend
- Banco Supabase UJN: `ujn_email_desk_imap_flag_jobs` (fila privada de flags, sem permissão direta do navegador).
- Leitura no Brain: ao abrir uma conversa nova ou escolher "Marcar como lido/não lido", a atualização de recibos passa a gerar job `SEEN` (ou desfazer `SEEN`).
- Seleção múltipla usa os mesmos recibos e dispara apenas para a mensagem recebida mais recente de cada conversa.
- **Respondida:** somente depois que o worker SMTP reportar `SENT` para uma resposta **REPLY** (não para encaminhamentos, rascunhos ou aprovações ainda QUEUED), o Supabase cria jobs `ANSWERED=true` e `SEEN=true`.
- Nada altera o IMAP até a instalação e execução do worker IMAP privado no cPanel.
- `ujn-email-desk-v1` v41: ações HMAC autenticadas `imap_flags_claim` e `imap_flags_report`. O navegador não pode invocar essas operações.
- `ujn_imap_incremental_collector.py`: inclui UID e UIDVALIDITY verificadas de novos e-mails da INBOX; e-mails antigos são procurados por `Message-ID` exato.
- `ujn_imap_flag_worker.py`: conexão TLS IMAP da mesma conta, seleção exclusivamente INBOX com permissão de escrita, UID SEARCH + verificação exata de Message-ID (ou UID validado com UIDVALIDITY), UID STORE `\\Seen` / `\\Answered`, ou remoção de `\\Seen`. Sem EXPUNGE, DELETE, MOVE, SMTP, cópia pública de credenciais ou alteração de outras pastas.
- Estado de processamento `PENDING` → `CLAIMED` → `DONE` / `FAILED`, com razão técnica e sem repetição automática de jobs ambíguos. Mensagens que saíram da INBOX podem exigir conferência manual.

## Instalação no cPanel `apolo.ojsbr.com`
Na pasta privada `/home/ujn/brain-ujn/`, colocar:
1. **Atualizar** `ujn_imap_incremental_collector.py` com a versão do GitHub (preservar arquivo original como backup).
2. **Adicionar** `ujn_imap_flag_worker.py` do GitHub. Deve ficar ao lado de `ujn_imap_readonly_collector.py` (este permanece inalterado).

**Sem Terminal**: no cPanel, criar uma quinta tarefa Cron temporária, frequência `* * * * *`, apenas para diagnóstico (uma vez):
```sh
if [ ! -f /home/ujn/brain-ujn/state/imap_flags_diagnose_once.flag ]; then touch /home/ujn/brain-ujn/state/imap_flags_diagnose_once.flag; /usr/bin/python3 -m py_compile /home/ujn/brain-ujn/ujn_imap_flag_worker.py /home/ujn/brain-ujn/ujn_imap_incremental_collector.py && timeout 45s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_flag_worker.py --diagnose > /home/ujn/brain-ujn/state/imap_flags_diagnose.log 2>&1; fi
```
Consultar `/home/ujn/brain-ujn/state/imap_flags_diagnose.log`, esperar `"imap_flags": "DIAGNOSTIC", "connection": "VERIFIED", "flags_changed": false`. Se falhar, **não habilitar** execução de flags. Excluir a tarefa temporária após o teste; não mexer nas quatro Cron permanentes.

Após diagnóstico aprovado, adicionar **uma única tarefa cron própria**, uma vez por minuto (todos os campos `*`):
```sh
timeout 95s /usr/bin/flock -n /home/ujn/brain-ujn/state/imap_flags_worker.cron.lock /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_flag_worker.py >> /home/ujn/brain-ujn/state/imap_flags_worker.log 2>&1
```
O processamento é incremental e deve gravar:
```json
{"imap_flags":"COMPLETE","jobs":1,"done":1,"failed":0,"unreported":0,"sent_email":false}
```
Exemplos de erros: `MESSAGE_NOT_IN_INBOX` (mensagem movida), `MESSAGE_ID_NOT_UNIQUE` (identidade ambígua), `UIDVALIDITY_MISSING`. Jobs nessas condições são marcados FAILED e exigem análise antes de qualquer retentativa.

## Homologação
1. Escolher uma mensagem **não lida** que está na INBOX do Roundcube.
2. Abrir a mesma conversa no Brain e confirmar mudança do recibo Brain; verificar no log `done>0`; atualizar Roundcube e confirmar estado lida.
3. Escolher resposta real aprovada pelo operador, enviar via SMTP supervisionado; aguardar `SENT`; verificar no log IMAP o processamento `ANSWERED`; atualizar Roundcube e confirmar ícone de mensagem respondida.
4. Marcar "não lida" no Brain e verificar que a flag `\\Seen` é removida da mensagem selecionada da INBOX.
5. Não testar envio SMTP enviando mensagens reais sem autorização; as ações de leitura não enviam e-mails.

## Limites
- No Roundcube, o estado de "respondida" resulta da flag IMAP `\\Answered`. A aparência depende da versão do tema.
- A operação atual atua sobre a **última mensagem recebida da conversa** para cada ação. A sincronização de todas as mensagens de um thread será uma melhoria adicional.
- Flag `Seen` é global por caixa IMAP; recibo Brain é por operador. Se vários operadores marcarem estados diferentes, a última ação aceita prevalece no Roundcube.
- A sincronização não retroage automaticamente para respostas muito antigas. Não é garantia de entrega/leitura do destinatário.
- A versão inicial não escuta mudanças feitas no Roundcube para refletir no Brain (direção Brain → Roundcube).
