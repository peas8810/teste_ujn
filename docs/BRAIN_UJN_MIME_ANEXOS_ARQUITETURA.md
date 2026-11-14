# Brain UJN — Arquitetura MIME e anexos
Data: 14/11/2026. Implantação progressiva, sem substituir os coletores nem o SMTP.

## Componentes aproveitados
- cPanel `/home/ujn/brain-ujn`: Python 3.6.8, coletor `ujn_imap_incremental_collector.py`, módulo `ujn_imap_readonly_collector.py`, credenciais JSON privadas.
- Supabase `leytqsyfrmzhectatcqm`: Edge Function `ujn-email-desk-v1` (`sync_message`, `attachment_url`); `ujn-email-attachment-ingest` (`sync_attachment`); tabelas `ujn_email_desk_messages`, `ujn_email_desk_attachments`; bucket privado `ujn-editorial-email-attachments`.
- Brain `brain/index.html`: sanitização de HTML e solicitação de links temporários (~120 s) para operador autenticado.
- Política: janela de **300 UIDs por pasta**, sem backfill ilimitado.

## Fluxo
1. Cron IMAP atual seleciona `INBOX` / `INBOX.Sent` como READ ONLY, `BODY.PEEK[]` não marca como lido.
2. Extrator Python `ujn_email_mime_adapter.py` percorre as partes MIME e extrai HTML e metadados de anexos.
3. `sync_message` existente grava HTML sanitizado e metadados associados ao `message_key`.
4. Para cada anexo permitido (até 7 MiB, soma até 14 MiB por mensagem, até 15 metadados), o Python envia conteúdo em base64 com HMAC assinado à Edge Function existente `ujn-email-attachment-ingest`.
5. Edge Function valida assinatura, associa ao `message_key` já sincronizado, verifica MIME/tamanho e salva no bucket privado com caminho SHA-256; marca `STORED`.
6. Brain exibe o anexo ao lado do e-mail e, sob autenticação, pede `attachment_url`; a Edge Function confere que o anexo pertence à conversa e emite URL temporária.
7. Se houver anexo não suportado, a interface informa metadados/indisponibilidade. Nada é exposto publicamente e não há envio de SMTP.

## Arquivos novos/atualizados no GitHub
- `integracoes/webmail/ujn_email_mime_adapter.py` — **novo**.
- `integracoes/webmail/ujn_imap_incremental_collector.py` — mesma rotina, com recurso opcional.
- `integracoes/webmail/ujn_email_mime_recover_recent.py` — recuperação manual dos até 300 UIDs recentes por pasta com cursor separado.
- `brain/index.html` — remove cartões redundantes quando existem metadados e arquivo efetivamente armazenado.

## Instalação segura
1. Salvar cópia do coletor existente no cPanel. Nunca transferir senhas ao GitHub.
2. Enviar os **três scripts Python** do diretório `integracoes/webmail/` para `/home/ujn/brain-ujn/`, substituindo somente `ujn_imap_incremental_collector.py`.
3. Em terminal do servidor (ou Cron temporário sem atividade de envio), validar a sintaxe dos três arquivos:
   ```sh
   /usr/bin/python3 -m py_compile /home/ujn/brain-ujn/ujn_email_mime_adapter.py /home/ujn/brain-ujn/ujn_imap_incremental_collector.py /home/ujn/brain-ujn/ujn_email_mime_recover_recent.py
   ```
4. O modo está **desativado por padrão**. Para ativá-lo **somente após validação**, editar o terceiro Cron atual (IMAP), mantendo a frequência de 1 min:
   ```sh
   UJN_IMAP_MIME_ENABLED=1 UJN_IMAP_ATTACHMENTS_ENABLED=1 UJN_IMAP_NEW_LIMIT=60 UJN_IMAP_MAX_SECONDS=95 timeout 110s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_incremental_collector.py >> /home/ujn/brain-ujn/state/imap_maildesk_cron.log 2>&1
   ```
5. Testar um e-mail novo com texto formatado, link HTTPS e PDF pequeno, verificando `body_html` e `STORED`. Restaurar o comando antigo sem flags se houver erro; a coleta de texto puro continua.
6. Para enriquecer **mensagens recentes já sincronizadas**, após o teste, executar manualmente em pequenos lotes (sem Cron adicional):
   ```sh
   UJN_IMAP_MIME_ENABLED=1 UJN_IMAP_ATTACHMENTS_ENABLED=1 /usr/bin/python3 /home/ujn/brain-ujn/ujn_email_mime_recover_recent.py --dry-run
   UJN_IMAP_MIME_ENABLED=1 UJN_IMAP_ATTACHMENTS_ENABLED=1 /usr/bin/python3 /home/ujn/brain-ujn/ujn_email_mime_recover_recent.py --limit 10
   ```
   A recuperação possui checkpoint próprio `state/mime_recover_recent.json`. Não toca o cursor da coleta normal.
7. Não alterar o Cron SMTP rápido nem criar tarefas paralelas para o mesmo IMAP.

## Verificação
```sql
select count(*) as mensagens, count(body_html) as html
from public.ujn_email_desk_messages
where mailbox='contato@ujn.ojsbr.com';
select availability,count(*) from public.ujn_email_desk_attachments group by availability;
```

## Restrições
- Anexos maiores que 7 MiB, tipos não autorizados e partes MIME adicionais além de 15 são ignorados no envio, preservando metadados quando possível.
- Proteções existentes no Supabase sanitizam HTML e restringem assinaturas HMAC. Links HTTPS em HTML são interativos, mas o conteúdo remoto (imagens externas) não deve ser carregado automaticamente.
- O carregamento de anexo não realiza análise antivírus; estabelecer varredura de malware e avisos ao operador antes de abrir arquivos de remetentes desconhecidos.
- O enriquecimento é opt-in para reduzir risco de carga excessiva e preservar disponibilidade da rotina IMAP e do SMTP.
