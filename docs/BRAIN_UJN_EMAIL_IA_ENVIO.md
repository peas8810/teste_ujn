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


## Melhoria de atualização IMAP — 14/11/2026

O novo arquivo `integracoes/webmail/ujn_imap_incremental_collector.py` implementa:
- Priorização de novas mensagens por UID, sem reler todas a cada execução.
- Recuperação gradual do histórico anterior em pequenos lotes (`backfill`).
- Checkpoints privados e atômicos em `/home/ujn/brain-ujn/state/maildesk_incremental_state.json`.
- Bloqueio de concorrência (`flock` interno) e proteção da pasta INBOX e Enviados.
- Reaproveitamento do módulo `ujn_imap_readonly_collector.py`, que deve permanecer no mesmo diretório.
- Consulta somente leitura, com `BODY.PEEK[]`, sem envio SMTP pelo coletor.

Edite a tarefa existente `imap_maildesk_cron.log` em vez de criar outra. Configure frequência de um minuto, com cinco campos * no cPanel. Substitua seu comando por:

```sh
UJN_IMAP_NEW_LIMIT=30 UJN_IMAP_BACKFILL_LIMIT=10 UJN_IMAP_MAX_SECONDS=95 timeout 110s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_incremental_collector.py >> /home/ujn/brain-ujn/state/imap_maildesk_cron.log 2>&1
```

O SMTP de um minuto permanece com o mesmo comando. Não mantenha o coletor IMAP antigo executando em paralelo como tarefa recorrente. Preserve os demais monitores anteriores do Brain até auditoria de suas funções.

Cada log traz `mode: incremental`, `new`, `historical`, `errors`, `sync_enabled` e `backfill_remaining`. O histórico completo pode levar várias horas. Enquanto `backfill_remaining=true`, não afirmar que todas as mensagens históricas foram coletadas.

A fila SMTP agora exige relatório IMAP recente (menos de quatro minutos), validação de Entrada e Enviados e ausência de erros. Não apague o arquivo de checkpoint e não aumente os limites de lotes sem medir o tempo de execução.
## Política de janela móvel de 300 — atualização 14/11/2026

- O coletor incremental carrega e acompanha **até os 300 UIDs mais recentes em cada pasta IMAP** (Entrada e Enviados), sem buscar os e-mails anteriores à janela atual. Não é um limite combinado de 300 mensagens entre pastas.
- O servidor entrega **até 300 conversas ativas** na vista principal. Respostas e casos arquivados saem dessa fila e continuam consultáveis na vista de histórico, com até 300 conversas por consulta.
- As novas mensagens entram a cada ciclo do Cron de um minuto. O checkpoint avança por UID; mensagens além da janela não são apagadas do Webmail ou do Supabase.
- O retorno de histórico foi desativado; o coletor não continuará a importar mensagens antigas só para completar o banco.
- Preserve `/home/ujn/brain-ujn/state/maildesk_incremental_state.json`. Não apague nem reinicie checkpoints apenas para forçar a fila a carregar do começo.
- Use apenas `ujn_imap_incremental_collector.py` no Cron principal de e-mails. Substitua o arquivo no cPanel pela nova versão; os demais programas do projeto não são afetados.

Configuração recomendada em **Editar** na tarefa IMAP já existente (todos os campos de tempo `*`):

```sh
UJN_IMAP_NEW_LIMIT=60 UJN_IMAP_MAX_SECONDS=95 timeout 110s /usr/bin/python3 /home/ujn/brain-ujn/ujn_imap_incremental_collector.py >> /home/ujn/brain-ujn/state/imap_maildesk_cron.log 2>&1
```

Não use mais `UJN_IMAP_BACKFILL_LIMIT=10`; a recuperação histórica está desativada na versão nova. A fila SMTP continua supervisionada e separada.

Nota: se 300 e-mails por pasta não forem suficientes para conciliar uma conversa antiga, ela poderá precisar de reimportação pontual mediante solicitação. O estado já salvo de mensagens antigas no banco permanece preservado.

## Envio SMTP mais rápido — monitoramento de fila a cada 10 segundos

A execução da fila pelo cPanel a cada minuto provocava esperas de até ~60 segundos. O teste de 14/11/2026 foi autorizado às 11:14:27 e confirmado como SENT às 11:15:05 (cerca de 38 segundos).

O novo `ujn_smtp_fast_runner.py` executa o `ujn_smtp_supervised_worker.py --send-one` aproximadamente a cada 10 segundos dentro de uma única janela Cron de um minuto.

- **Instalar** o arquivo `integracoes/webmail/ujn_smtp_fast_runner.py` em `/home/ujn/brain-ujn/`, sem substituir o worker SMTP existente.
- **Editar**, e não duplicar, a tarefa Cron SMTP de um minuto. O único comando SMTP agendado deve ser:

```sh
timeout 100s /usr/bin/python3 /home/ujn/brain-ujn/ujn_smtp_fast_runner.py >> /home/ujn/brain-ujn/state/smtp_maildesk_dispatch.log 2>&1
```

- Manter os cinco campos de periodicidade Cron em `*`.
- Não alterar o Cron IMAP (um minuto).
- O runner mantém lock em `state/smtp_fast_runner.lock` para impedir duas instâncias simultâneas. O worker somente envia solicitações `QUEUED` aprovadas, registrando `SENT`, `FAILED` ou `UNKNOWN` no banco, sem reprocessar automaticamente trabalhos reivindicados.
- Se o processo exceder o tempo configurado, pode haver atraso superior a 10 segundos; trata-se de consulta periódica (polling), não envio instantâneo.
- O Brain UJN consulta o estado do envio a cada 3 segundos enquanto existir uma solicitação pendente, exibindo `QUEUED`, `CLAIMED` e `SENT`.
- Se ocorrer `WORKER_ERROR`, `WORKER_TIMEOUT`, `FAILED` ou `UNKNOWN`, não reenvie a solicitação sem conciliar com a pasta Enviados.

Atualize o painel com Ctrl+F5 depois de alterar o Cron. Antes de ativar outro envio real, verifique o log do runner com a fila vazia. Não instale uma segunda tarefa Cron de SMTP.