# Brain UJN — Caixa de e-mails, IA e envio supervisionado

## Integração implantada

Frontend: `brain/index.html`, navegação Operação → **E-mails · IA e envios**. Mesma sessão do Brain UJN/Academy. O servidor UJN confirma, em duas instâncias separadas, se a pessoa é (1) superadministradora da Central Academy e (2) operadora ativa do UJN Intelligence, com **o mesmo e-mail confirmado**.

Backend de e-mail: Supabase UJN Intelligence, função `ujn-email-desk-v1`, tabelas `ujn_email_desk_threads`, `ujn_email_desk_messages`, `ujn_email_desk_drafts`, `ujn_email_desk_send_queue`.

A aprovação é por mensagem, exige destinatário igual ao correspondente cadastrado e bloqueia o envio se já houver resposta posterior. O dispatcher usa HMAC, retira no máximo um item por execução, não reenvia automaticamente tentativas de resultado incerto e registra o resultado `SENT`/ `FAILED` / `UNKNOWN`. Respostas novas têm `In-Reply-To` e `References` quando há Message-ID anterior; o worker tenta arquivar a mensagem na pasta `\\Sent` do IMAP.

**Status em 14/11/2026**: autenticação IMAP confirmada, SMTP 465 confirmado, entrega de e-mail de teste ao Gmail confirmada. O banco está com `smtp_enabled=true` e `sync_enabled=false`. Não há rotina cron provisionada pelo GitHub: o executor depende do cPanel.

## Ações pendentes no cPanel

### 1. Atualizar ambos os arquivos privados

Baixe a versão **mais atual** do GitHub e substitua:
- `integracoes/webmail/ujn_imap_readonly_collector.py` → `/home/ujn/brain-ujn/ujn_imap_readonly_collector.py`
- `integracoes/webmail/ujn_smtp_supervised_worker.py` → `/home/ujn/brain-ujn/ujn_smtp_supervised_worker.py`

Não toque nos arquivos privados `imap_config.json` ou `ingest_config.json`. Não exponha senha nem chave HMAC em repositório público.

### 2. Agendar a leitura IMAP

Em **Tarefas Cron**, agende a cada 5 minutos (`*/5 * * * *`) com o comando abaixo:

```sh
UJN_IMAP_SCAN_LIMIT=30 timeout 180s python3 /home/ujn/brain-ujn/ujn_imap_readonly_collector.py > /home/ujn/brain-ujn/state/imap_maildesk_cron.log 2>&1
```

O coletor lê `INBOX` e tenta descobrir automaticamente a pasta Enviados. A leitura é somente leitura (`BODY.PEEK[]`); não altera flags nem envia respostas. A API deduplica pelo `Message-ID`. O limite de 30 mensagens por pasta em cada execução é uma janela de amostragem, **não** sincronização completa de todos os e-mails históricos.

O próprio coletor envia um relatório HMAC assinado de saúde da INBOX e da pasta Enviados. O Supabase define `sync_enabled=true` **automaticamente** somente após ambas as pastas serem verificadas e não haver erros; não ative manualmente.

### 3. Agendar dispatcher SMTP

Em **Tarefas Cron**, agende a cada minuto (`* * * * *`) com:

```sh
timeout 90s python3 /home/ujn/brain-ujn/ujn_smtp_supervised_worker.py --send-one >> /home/ujn/brain-ujn/state/smtp_maildesk_dispatch.log 2>&1
```

`--send-one` não manda e-mail sem uma solicitação `QUEUED` aprovada por operador. Além disso, somente retira itens depois de `smtp_enabled=true`, `sync_enabled=true` e `sent_folder` validado. Antes do primeiro diagnóstico IMAP assinado, o log pode exibir `{"ready":false,"dispatched":0}`. Quando saudável e sem fila, será `{"ready":true,"dispatched":0}`.

O teste `--send-test` anterior deve ficar DESATIVADO, sem Cron recorrente. **Não apague** `state/smtp_test_once.lock` apenas para repetir envio.

### 4. Homologação operacional

1. Abra `https://peas8810.github.io/teste_ujn/brain/` e autentique-se como superadministrador.
2. Clique **E-mails · IA e envios**.
3. Atualize a lista, abra uma mensagem e gere uma sugestão com IA.
4. Revise assunto, destinatário e corpo. Não autorize um envio a terceiro sem necessidade editorial legítima.
5. Quando houver uma resposta real devidamente autorizada, confirme que ela passou por `QUEUED → CLAIMED → SENT`, com `sent_archive=ARCHIVED` quando a pasta Sent existir.
6. Verifique no Webmail e na Central o histórico final.

## Limitações e cuidados

- A rotina SMTP só entra em operação depois de o arquivo atual estar no cPanel e o Cron estar configurado.
- A pasta Enviados ainda precisa ser confirmada através dos logs do primeiro teste operacional.
- Sem sincronização IMAP completa, o indicador “aguardando resposta” é **provisório**; não deve ser usado como decisão definitiva. A fila de envios permanece bloqueada até que Entrada e Enviados tenham sido detectadas e sincronizadas sem erro.
- A autenticação cruzada só permite acesso por superadministrador Academy com e-mail confirmado e vínculo ativo de operador UJN. A autenticação Academy não substitui a verificação de autorização no banco UJN.
- O worker não tenta repetir uma mensagem que já entrou em execução e ficou em status `UNKNOWN`, para evitar duplicidade de envios.
