# Brain UJN — Sincronização bidirecional de leitura e respostas do Roundcube (16/11/2026)

## Problema
Operadores respondem e marcam mensagens como lidas diretamente no Roundcube, mas o Brain UJN ainda mostra os mesmos e-mails como não lidos/aguardando atendimento. A sincronização existente era Brain -> Webmail (UID STORE por fila), sem observação periódica IMAP -> Brain.

## Implantado
1. Banco `ujn_email_desk_messages`: novos campos `imap_seen`, `imap_answered`, `imap_flags_checked_at` (todos inicialmente nulos).
2. PostgreSQL RPC `ujn_email_desk_apply_remote_imap_flags`: recebe lote de até 120 observações autenticadas por service_role, associa pelo Message-ID exato e atualiza as flags. Se houver alteração local pendente `PENDING/CLAIMED` para a mensagem, a observação é ignorada temporariamente. Quando `\\Answered` estiver presente na **última mensagem recebida da conversa**, muda a situação da conversa para ANSWERED, sem sobrescrever estados como arquivado ou revisão humana.
3. RPC `ujn_email_desk_thread_remote_read`: apresenta as flags da última mensagem recebida em cada conversa à API, sem acesso público.
4. Edge Function `ujn-email-desk-v1` v45: HMAC `imap_flags_observe`, exclusivo do coletor; lista de conversas passa a calcular `unread` considerando o estado IMAP mais recente e alterações locais posteriores.
5. `brain/index.html`: exibe sincronização com Webmail, lida/respondida no painel e sinaliza quando não houve primeira sincronização.
6. `integracoes/webmail/ujn_imap_incremental_collector.py`: usa a conexão IMAP readonly que já existe, sem outro Cron. A cada execução lê flags de até 60 mensagens do lote recente de 300 (dividido em cinco partes por minuto); envia por HMAC à Edge Function. Tempo limite existente, sem reduzir o sincronismo normal de novos emails.

## Instalação necessária no cPanel
Substituir **somente** o arquivo `/home/ujn/brain-ujn/ujn_imap_incremental_collector.py` pela versão atualizada do GitHub. Não mudar `imap_config.json`, `ingest_config.json`, `ujn_imap_flag_worker.py` ou Cron atuais. O Cron incremental original já define `UJN_IMAP_MIME_ENABLED=1` e `UJN_IMAP_ATTACHMENTS_ENABLED=1`. A função nova não envia e-mail nem atualiza flags IMAP, só as observa.

## Homologação
1. Atualizar o arquivo do coletor no cPanel; **não criar sexto Cron**.
2. Verificar `state/imap_maildesk_cron.log` após execução. O JSON deve conter `webmail_flags` com `observed`, `updated`, `errors`.
3. Se `observed` for zero em um ciclo, pode ser que a fração de UIDs esteja vazia, o servidor tenha recusado FLAGS ou o prazo da execução tenha expirado. Consultar `errors`.
4. Verificar no Supabase o total de mensagens com `imap_flags_checked_at is not null`. O valor atual é **zero antes da atualização do coletor**.
5. Abrir no Brain uma mensagem da INBOX que foi marcada lida/respondida pelo Roundcube; após o ciclo de leitura da respectiva fração de UIDs e atualização da página, não deve aparecer como não lida nem aguardando equipe caso o IMAP tenha `\\Answered`.
6. Se o cliente Webmail enviar uma resposta mas não marcar o email com `\\Answered`, a confirmação poderá depender da importação do e-mail enviado; o código nunca presume uma resposta apenas porque a mensagem foi lida.
7. Mensagens movidas para Arquivo, removidas da INBOX ou fora da janela de 300 UIDs não são garantidas pela observação corrente. A integração histórica dessas pastas exigiria rotina de recuperação separada e autorizada.

## Segurança
- IMAP `SELECT readonly=True`, `BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)]` e FETCH de FLAGS somente leitura.
- Reusa HMAC e chave já privadas no servidor; não expõe tokens no navegador.
- Credenciais não enviadas a GitHub, nem novos Cron.
- Não altera conteúdo, anexos, destinatários ou mensagens enviadas.
- Sistema em produção não depende do retorno da consulta para receber emails: falha de leitura de flags gera alerta no log, não cancela o sincronismo existente.
- Sintaxe de frontend conferida e migração/RPC presentes no Supabase; o teste ponta a ponta da leitura real depende de atualizar o script no cPanel.
