# Brain UJN — Respostas endereçadas pelo cabeçalho RFC 5322 Reply-To

Data: 15/11/2026

## Escopo e incidente
A Central de E-mails enviou uma mensagem marcada como SENT para `ujn@journals.ojsbr.com`, remetente técnico de uma notificação OJS, quando a resposta humana deveria ir para o endereço indicado em `Reply-To` (Douglas). `SENT` é confirmação do executor SMTP, não de leitura ou entrega ao destinatário final. Não reenviar automaticamente.

## Política de envio implementada
1. Ler o cabeçalho **Reply-To** de cada mensagem recebida. Quando houver exatamente um endereço sintaticamente válido, ele terá preferência sobre From.
2. Se não houver Reply-To, utilizar **From** apenas quando houver exatamente um remetente e ele não for um endereço técnico/bloqueado.
3. Bloquear automaticamente ambiguidades, múltiplos destinatários Reply-To, endereços técnicos, no-reply e mensagens antigas cujo cabeçalho ainda não tenha sido verificado.
4. Exibir claramente no Brain **Recebido de** e **Responder para** e destacar divergências para revisão do operador. O campo do destinatário não pode ser editado para contornar esta verificação.
5. A autorização humana continua obrigatória. A função SQL `ujn_email_desk_approve_send` verifica o destinatário contra a **última mensagem recebida**. A função `ujn_email_desk_claim_send` confere novamente imediatamente antes do SMTP. Se mudar, cancela a autorização não enviada.
6. Mesmos mecanismos aplicados ao `brain/index.html` e `central-emails/index.html`.
7. Essas garantias cobrem o **SMTP supervisionado da Central Brain UJN**, não qualquer serviço externo ou cliente de e-mail fora dela.

## Componentes publicados
- `integracoes/webmail/ujn_imap_incremental_collector.py`: função `reply_routing` grava `reply_to`, `reply_to_name`, `reply_to_source` em `sync_message` para cada e-mail inbound; read-only, sem disparo SMTP.
- `integracoes/webmail/ujn_email_mime_recover_recent.py`: `--reply-to-reconcile`, checkpoint próprio; recupera de maneira incremental cabeçalhos das últimas 300 mensagens da INBOX, sem uploads MIME.
- `ujn-email-desk-v1`: endpoint verifica e atualiza destinatários apenas por ingestão HMAC, retorna `reply_target` verificado e rejeita cabeçalhos ambíguos.
- RPCs SQL `ujn_email_desk_approve_send` e `ujn_email_desk_claim_send`: política *fail closed*.
- Painéis Brain UJN e Central de E-mails: exibição segura.

## Passos no cPanel (sem Terminal)
Instalar os dois arquivos Python acima em `/home/ujn/brain-ujn/` e substituir as versões anteriores. Não alterar os quatro cron de produção.

Para conciliar as últimas 300 mensagens **anteriores** da INBOX, adicionar uma tarefa Cron TEMPORÁRIA, com todos os campos `*` e comando:
```sh
if [ ! -f /home/ujn/brain-ujn/state/reply_to_reconcile_done.flag ]; then sleep 20; UJN_IMAP_MIME_ENABLED=0 UJN_IMAP_ATTACHMENTS_ENABLED=0 timeout 45s /usr/bin/python3 /home/ujn/brain-ujn/ujn_email_mime_recover_recent.py --reply-to-reconcile --limit 10 >> /home/ujn/brain-ujn/state/reply_to_reconcile.log 2>&1; fi
```
- Coleta apenas metadados necessários, sem tocar nos flags de leitura IMAP, sem editar cursors do coletor principal e **sem SMTP**.
- Compartilha lock com o incremental; resultados `ALREADY_RUNNING` em colisões são seguros, a próxima execução tentará novamente.
- Estado da recuperação em `state/mime_recover_recent.json`, chave `reply_to_reconcile`. O arquivo `reply_to_reconcile_done.flag` é gerado automaticamente após processar as 300 mensagens recentes sem erros.
- Excluir esta quinta tarefa temporária após o log confirmar `"completed": true`. Manter os quatro Cron originais.
- E-mails antigos fora da janela de 300 permanecem sem verificação e com resposta bloqueada. Necessitam conciliação pontual futura; **não inferir destinatário** com base no assunto.

## Teste de aceitação
1. Notificação OJS com From técnico e Reply-To de um pesquisador: mostrar os dois endereços, autorizar resposta somente ao Reply-To.
2. E-mail comum sem Reply-To: responder ao From validado.
3. E-mail com Reply-To múltiplo ou malformado: bloquear e solicitar revisão humana.
4. Mudança de Reply-To da última mensagem entre autorização e dispatch: cancelar envio antes de SMTP.
5. Nenhum envio automático e nenhum reenvio do caso anterior.
