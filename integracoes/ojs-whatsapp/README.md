# Brain UJN — Notificações OJS → WhatsApp

**Status em 09/11/2026:** infraestrutura de coleta em homologação; envios externos **desativados** até confirmação de consentimento, templates aprovados pela Meta e instalação dos hooks OJS. Sistema independente do ACADEMY.

## Arquitetura

1. Cada revista (REMUNOM, JIRRS, NEXUS, RSV, RJNM) envia um evento editorial assinado à função `ujn-editorial-ojs-events`.
2. A função valida assinatura HMAC SHA-256 exclusiva da revista e impede o processamento repetido do mesmo identificador.
3. O evento é registrado no Supabase de homologação, associado ao código da revista e ID da submissão.
4. Destinatários precisam ter telefone `+E164`, prova de consentimento e identidade verificada. Apenas essas inscrições geram rascunhos de entrega.
5. Um envio definitivo exigirá modelo **Utility** aprovado na conta Meta da Editora UJN, checagem de revogação, idempotência, limite de frequência e confirmação do provedor.
6. E-mails OJS continuam independentes e não devem ser alterados.

## Evento de exemplo (sem dados confidenciais)

```json
{
  "event_id": "rjnm-submission-8267-copyediting-20261109T194000Z",
  "submission_id": 8267,
  "event_type": "copyediting_started",
  "occurred_at": "2026-11-09T19:40:00Z",
  "title": "Título do manuscrito",
  "doi": "10.66104/gdmjsm29"
}
```

A assinatura é `sha256=hex(HMAC_SHA256(secret, timestamp + "." + json_body))`. Headers: `x-ujn-journal`, `x-ujn-timestamp` (Unix segundos), `x-ujn-signature` e `Content-Type: application/json`. O relógio do servidor deve estar sincronizado, com tolerância de 5 minutos. Segredos diferentes para cada revista devem ser obtidos por um administrador autorizado e configurados no servidor do OJS, **nunca** no front-end.

## Integração ao OJS

O arquivo `EditorialWhatsAppRelay.php` é apenas o transporte HTTP seguro. A hospedagem de cada revista precisa instalar o módulo de hooks compatível com a versão exata do OJS e chamar `UjnEditorialWhatsAppRelay::deliver()` após o evento ter sido persistido. Não chamar no início da transação nem assumir que todas as mensagens internas são direcionadas ao autor.

Eventos aceitos: `submission_received`, `editor_assigned`, `review_started`, `review_round_created`, `review_requested`, `review_completed`, `revision_requested`, `revision_submitted`, `editor_message_available`, `author_message_available`, `editorial_decision`, `accepted`, `declined`, `copyediting_started`, `production_started`, `proof_requested`, `proof_approved`, `published`, `publication_updated`, `withdrawn`, `other_activity`.

**Nunca enviar ao WhatsApp:** texto de pareceres, identidade de avaliadores em revisão anônima, anexos confidenciais, dados privados de outros autores ou links internos de edição. Avisos de mensagem/parecer devem dizer apenas que há uma comunicação disponível para o autor consultar no OJS.

## Fallback por leitura OJS

A função `ujn-editorial-wa-poll` detecta mudanças amplas de estágio, situação, início de rodada e publicação, comparando snapshots dos artigos com assinantes elegíveis. A primeira leitura estabelece baseline e não deve gerar notificações retroativas. **Polling não garante capturar todas as movimentações**, especialmente várias mensagens entre verificações: para paridade com os e-mails o webhook de eventos OJS é necessário.

## Notificação genérica proposta para aprovação na Meta

Template sugerido: `ujn_editorial_update_ptbr`, categoria **UTILITY**, idioma `pt_BR`.

> Olá, {{1}}. A revista {{2}} registrou uma atualização na sua submissão {{3}}: {{4}}. Acesse o sistema editorial para consultar os detalhes. Para interromper os avisos por WhatsApp, responda PARAR.

É somente uma proposta de template. Não afirmar aprovação. Acesso a detalhes do processo editorial exige autenticação no OJS.

## Pendências antes de habilitar envio

- Confirmar campo de telefone e consentimento opt-in em cada OJS. Não presumir que cadastrar telefone = consentimento Meta.
- Vincular cada `journal_code + submission_id` ao telefone do autor correspondente mediante prova e validação.
- Instalar hooks/relay no servidor OJS das cinco revistas e homologar pelo menos um evento de cada tipo.
- Aprovar template no WhatsApp Manager e confirmar a conta da Meta responsável pelo número UJN.
- Construir despachante de produção com fila idempotente, limite de frequência, opt-out e retorno de status de entrega.
- Validar desativação/retomada e falhas antes de ligar `delivery_enabled`.


## Implementação executada — atualização 09/11/2026

Todos os cinco sites anunciaram **Open Journal Systems 3.5.0.5** no meta `generator`. Foi criada uma estrutura central compartilhada:
- `ujn-editorial-ojs-events`: eventos assinados HMAC e inscrição/cancelamento consentidos vindos dos servidores OJS
- `ujn-editorial-wa-poll`: consulta periódica de transições de estágio/status para inscrições verificadas
- `ujn-editorial-wa-dispatch`: fila de envios aprovados, revalidação de consentimento, concorrência e idempotência
- `ujn-editorial-template-gateway`: canal Meta da Editora UJN, envio **somente via template** `ujn_editorial_update_ptbr`
- `ujn-editorial-wa-optout`: cancelamento por telefone; mensagem PARAR interceptada no WhatsApp UJN

### OJS 3.5 — arquivos preparados, ainda não instalados nos servidores

O diretório `plugin-ojs35/` contém um plugin genérico para a versão 3.5.0.5. É uma **primeira versão**, que cobre:
- `Submission::add` → evento `submission_received`
- `Decision::add` → evento `editorial_decision`

Esses dois hooks são compatíveis com os nomes documentados do OJS. Entretanto, instalar arquivos no GitHub **não os instala nos cinco OJS**. É necessário acesso ao servidor/gerenciador de plugins e testes de compatibilidade em homologação. E-mails OJS não são alterados.

**Ainda não conectados ao plugin:** mensagens de discussão/pareceres, comentários do editor, pedidos de prova, prazos de revisão e eventos específicos de cada comunicação. Os eventos são aceitos na API, mas exigem hooks adicionais ou um mecanismo institucional no OJS que os emita após a gravação. Não confundir “evento aceito pela API” com “evento efetivamente detectado na revista”.

### Instalação pelo responsável técnico do OJS

1. Copiar os quatro arquivos de `plugin-ojs35/` para `plugins/generic/ujnEditorialWa/` em cada instalação OJS 3.5.0.5; verificar que o mecanismo de autoload do OJS encontra a classe.
2. Definir **no ambiente do servidor**, não em HTML nem GitHub: `UJN_OJS_WA_JOURNAL` = código exato da revista e `UJN_OJS_WA_SIGNING_KEY` = chave exclusiva do webhook. Obter a chave no cofre Supabase por método administrativo seguro, não registrá-la em logs.
3. Habilitar o plugin na administração do OJS, confirmar hooks e validar a criação de evento com uma submissão de teste.
4. Preparar o opt-in explícito dos autores no formulário institucional. A chamada assinada `subscription_opt_in` aceita `submission_id`, `phone_e164`, `recipient_role: corresponding_author`, `consent_at`, `consent_source: ojs_author_optin`, `consent_evidence_ref: ojs:...`. Não cadastrar destinatários apenas por possuírem telefone no perfil.
5. Registrar/revisar o template Utility `ujn_editorial_update_ptbr` em português do Brasil no WhatsApp Manager, e só configurar `ujn_channels.template_name` após aprovação real.
6. Realizar homologação com consentimento de uma conta de teste por revista; verificar duplicatas e o comando `PARAR`; somente então habilitar `delivery_enabled` no banco após aprovação administrativa.

### Estado do banco em 09/11/2026

`polling_enabled=true`; `delivery_enabled=false`. Fila do dispatcher ativa a cada 5 minutos, mas com envio bloqueado. A API editorial possui cinco chaves de webhook distintas. Não há assinantes cadastrados na fila nova. Não foram enviados WhatsApps automáticos editoriais.

**Atenção a produção:** o plugin é um ponto inicial para homologação e não substitui os testes de instalação no OJS. Não expõe identidades de pareceristas nem o conteúdo dos pareceres. Para entregar “cada movimentação”, ainda é necessária a conexão dos eventos de correspondência internos em todas as revistas.


## Alternativa sem plugin: Webmail/SMTP → IMAP → WhatsApp

Foi criado um coletor independente: imap_collector.py. Requer Python 3.11+, IMAPS na porta 993, HTTPS e agendamento na hospedagem, mas não altera OJS nem Academy.

Atenção: SMTP não significa que a caixa do remetente guarde uma cópia da mensagem enviada ao autor. Configure BCC/roteamento de mensagens editoriais com o provedor, preservando o destinatário original no campo To. Se encaminhar de modo que o To fique como a caixa monitorada, o coletor rejeita, por não saber quem é o autor.

Endpoint ativo: https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-editorial-email-ingest

Configuração necessária em servidor seguro:
- UJN_JOURNAL = RJNM, REMUNOM, RSV, JIRRS ou NEXUS
- UJN_IMAP_HOST = hostname da caixa de monitoramento
- UJN_IMAP_USER = usuário da caixa
- UJN_IMAP_PASSWORD = senha de aplicativo guardada no servidor
- UJN_IMAP_FOLDER = INBOX
- UJN_EMAIL_INGEST_HMAC = chave do Vault Supabase obtida por administrador autorizado
- UJN_DRY_RUN = 1 para teste sem gravação

Configuração do Supabase: em ujn_editorial_email_sources, habilitar revista e cadastrar o endereço exato do remetente autorizado; sem isso a função rejeita mensagens. Associação do destinatário exige hash SHA-256 do e-mail, ID de submissão, telefone E.164, consentimento registrado e vínculo verificado. Nome do autor isolado não é suficiente.

Teste confirmado: payload de e-mail fictício assinado com HMAC identificou revisão solicitada na submissão 8267 (HTTP 200, zero mensagens enviadas). O coletor ainda não foi executado em IMAP real: falta host, usuário e credenciais locais. O corpo completo e assunto não são salvos no banco.

O sistema gera apenas rascunhos de entrega PENDING_APPROVAL para destinatários confirmados. delivery_enabled permanece false. A Meta precisa aprovar o template editorial Utility antes da ativação de disparos. Mensagens desconhecidas e IDs ambíguos exigem revisão.

### Webmail informado — 09/11/2026

Captura de configuração cPanel/Webmail: conta contato@ujn.ojsbr.com; IMAPS mail.ujn.ojsbr.com:993 (SSL/TLS); SMTP mail.ujn.ojsbr.com:465. A senha não foi gravada nem usada na implantação. Por ter sido compartilhada no chat, é necessário trocá-la antes de usar o coletor.

Arquivo de exemplo sem segredos: imap.env.example. Rodar o coletor em servidor seguro com senha e chave HMAC inseridas por meio de variáveis de ambiente (não importar arquivo público).

**Pré-requisito ainda não verificado:** confirmar se a caixa recebe cópias dos e-mails que o OJS envia aos autores. A configuração de SMTP não demonstra que a caixa de entrada contém mensagens enviadas. Se necessário, pedir ao provedor da hospedagem uma regra de cópia de saída / journaling / BCC que preserve o endereço do autor. A caixa normal de enviados também só funciona se o sistema SMTP salvar cópia com o destinatário original.

Não ativar a ingestão para as cinco revistas apenas porque foi informada uma conta central: confirmar quais remetentes são usados em cada revista, se a caixa é de monitoramento e quais eventos serão copiados. Os registros em ujn_editorial_email_sources devem permanecer com enabled=false até homologação.

Requisitos para disparos: template Meta aprovado, opt-in e telefone do autor verificados, testes de deduplicação e entrega, e a flag delivery_enabled somente depois da validação.


## Leitura direta da caixa institucional por IMAP — 10/11/2026

A implementação atual não depende do filtro do cPanel ou da conta notificacoes@ujn.ojsbr.com. O script direct_inbox_collector.py utiliza mail.ujn.ojsbr.com:993, pasta INBOX, somente leitura, e identifica mensagens ao autor pela revista, assunto, URL e destinatário original.

### Instalação segura no cPanel

1. Remover o filtro Brain_UJN_Notificacoes da caixa contato@ujn.ojsbr.com, após confirmar que nada depende dele, porque não é usado nesta solução.
2. Substituir a senha antiga de contato@ujn.ojsbr.com (foi exposta na conversa). Nunca adicionar a senha nova ao GitHub/chat.
3. Criar no Gerenciador de Arquivos /home/ujn/brain-ujn e /home/ujn/brain-ujn/state fora de public_html. Colocar direct_inbox_collector.py no primeiro diretório.
4. Criar arquivo privado de configuração (permissões 0600) a partir de direct-imap.env.example. Guardar UJN_IMAP_PASSWORD e UJN_EMAIL_INGEST_HMAC somente no servidor; obter a chave HMAC do Vault Supabase administrativamente, sem divulgá-la.
5. Confirmar Python 3.11+ na hospedagem. Executar primeiro com UJN_DRY_RUN=1. Nesse modo a API somente classifica exemplos sem gravar ou enviar WhatsApp.
6. Depois, manter delivery_enabled=false no Supabase e passar a UJN_DRY_RUN=0 para estabelecer o cursor da caixa (baseline) sem processar o histórico. As próximas execuções processam somente mensagens novas.
7. Programar em cPanel → Avançado → Tarefas Cron a cada 5 minutos, com wrapper privado que carrega as variáveis sem expor a senha na linha Cron. Use flock para evitar jobs simultâneos.
8. Habilitar cada fonte de e-mail no Supabase somente depois de confirmar o remetente autorizado de cada revista, a entrega real no IMAP e o vínculo do destinatário com uma submissão.

### Segurança e limites

Mensagens com destinatário editor/institucional são ignoradas, assim como e-mails de remetente desconhecido ou revista ambígua. Sem ID único e autor correspondente validado, não há envio. O script não altera flags de leitura, não apaga, não move e não salva conteúdo integral no banco. Telefone, opt-in e template da Meta continuam pré-requisitos.

Teste já efetuado: endpoint de classificação recebeu um evento fictício REMUNOM com link workflowSubmissionId=8363 e retornou HTTP 200, submission_received, ID reconhecido e zero envios. A conexão IMAP real NÃO foi executada: é necessário configurar senha substituída no servidor do cPanel.


## Atualização 10/11/2026 — Python 3.6.8 do cPanel

O servidor da UJN tem /usr/bin/python3 = 3.6.8. O script **direct_inbox_collector.py foi atualizado** para suportar essa versão (o argumento timeout da biblioteca IMAP foi removido). O arquivo que estava instalado antes da atualização precisa ser substituído pelo arquivo atual do GitHub.

Primeiro, testar sem configurar credenciais nem acessar e-mails. Agendar TEMPORARIAMENTE uma execução via Cron de:

    /usr/bin/python3 /home/ujn/brain-ujn/direct_inbox_collector.py --self-test > /home/ujn/brain-ujn/state/self-test.txt 2>&1

O autoteste realiza parsing de uma mensagem fictícia, verifica o bloqueio de destinatários administrativos e produz JSON com self_test: ok, network_calls: 0 e whatsapp_sent: 0. Remover a tarefa temporária imediatamente depois de ler o resultado.

**Não habilitar o Cron de produção ainda.** Para IMAP real faltam: senha renovada e configuração privada, chave HMAC do Vault, um modo de carregamento seguro de variáveis, baseline confirmada e autorização de destinatários. Nenhuma chave/senha deve ser enviada pelo chat, inserida no código Python ou escrita na linha do Cron.

A função Supabase de classificação foi testada com mensagem fictícia de submissão REMUNOM e retornou HTTP 200 com ID correto; não representa um teste IMAP autenticado.


## Verificacao IMAP com Python 3.6.8 (sem ativar WhatsApp)

Foi adicionado [imap_probe.py](imap_probe.py) e [imap_config.example.json](imap_config.example.json). A ferramenta confirma a autenticacao IMAP e conta mensagens, mas nao le conteudo e nao envia notificacoes.

Copie o script para /home/ujn/brain-ujn/imap_probe.py. Crie /home/ujn/brain-ujn/imap_config.json copiando o exemplo e preencha a senha **somente pelo editor do cPanel**, fora de public_html. Defina permissao 0600 para esse arquivo privado. Nao envie senha pelo chat nem registre em GitHub.

Execute em tarefa Cron TEMPORARIA (uma vez por minuto):

    /usr/bin/python3 /home/ujn/brain-ujn/imap_probe.py > /home/ujn/brain-ujn/state/imap-probe.log 2>&1

Leia /home/ujn/brain-ujn/state/imap-diagnostico.json. Quando o status for OK, o login e a leitura INBOX estao confirmados. Exclua a tarefa temporaria apos obter o resultado.

A rotina de envio WhatsApp permanece desligada no Supabase. O diagnostico nao equivale a integrar os cinco OJS, aprovar destinatarios ou agendar o coletor definitivo.


## Fechamento auditado em 10/11/2026 — monitor e fila editorial

O Cron `*/5 * * * *` do cPanel está operacional em Python 3.6.8, com leitura IMAP da caixa institucional em modo somente leitura. A baseline foi estabelecida e um e-mail novo foi examinado sem envio (status OK; ignored=1).

O arquivo [imap_monitor.py](imap_monitor.py) agora inclui contadores agregados `reasons` para descartes e `journals` para candidatos identificados; continua sem registrar endereço ou corpo nos logs. Substituir o arquivo do cPanel pelo atual **sem apagar a pasta state ou o banco SQLite**, preservando o cursor e evitando reprocessar histórico. Não é necessário recriar o Cron.

### Integração do Supabase confirmada

- `ujn-editorial-email-ingest`: recebe eventos com HMAC; classifica e evita duplicidade, prepara rascunhos somente quando há correspondência inequívoca revista + submissão + hash do e-mail e opt-in verificado.
- `ujn-editorial-wa-poll`: existe para consulta OJS por API de submissões consentidas e criação de rascunhos em mudanças de status.
- `ujn-editorial-wa-dispatch`: exige flag `delivery_enabled=true`, registro aprovado (`READY`), consentimento, verificação e template; a flag continua **false**.
- Auditoria SQL: as cinco fontes `ujn_editorial_email_sources` continuam `enabled=false` e `allowed_sender_addresses=[]`; `ujn_editorial_wa_recipients` continua vazia. Não ativar envios antes da homologação.

### Bloqueadores reais para produção

1. **Cobertura**: `contato@ujn.ojsbr.com` não recebe necessariamente as notificações direcionadas aos autores; ler esta caixa isoladamente não captura automaticamente todas as movimentações dos cinco OJS. É necessário evento gerado pelo OJS para autores, cópia legítima de cada notificação ou sondagem API autenticada por submissão; não afirmar cobertura integral a partir de e-mails ao editor.
2. **Identidade**: cadastrar autores consentidos, com telefone E.164, revista, ID OJS, hash de e-mail, evidência do consentimento e verificação. Não inferir telefone da assinatura de um e-mail ou cruzar nomes iguais.
3. **Template Meta**: aprovar `ujn_editorial_update_ptbr`, mapear variáveis permitidas e validar número oficial em homologação. Não incluir pareceres ou links internos administrativos nas mensagens.
4. **HMAC e execução**: usar secret privado apenas no cPanel, sem publicá-lo em GitHub. A rotina atual `imap_monitor.py` é monitor local; não faz POST para ingest. Habilitar e testar a ponte assinada separadamente antes de ativar fontes.
5. **Governança**: manter eventos como `PENDING_APPROVAL` até aprovação explícita, impedir duplicidades, acompanhar falhas e opt-out; somente então considerar liberar `delivery_enabled`.

### Critérios de aceite

- Teste real de cada uma das cinco revistas com submissão de homologação e destinatário autorizado; sem envio a terceiros não autorizados.
- Simular os estados submissão, revisão, nova comunicação, decisão, edição e publicação; garantir que uma única mudança gera no máximo um rascunho por autor elegível.
- Confirmar os dois caminhos: IMAP (somente mensagens efetivamente recebidas) e polling OJS (para submissões monitoradas), sem dados privados no WhatsApp.
- Auditar entrega com recibos da Meta, erros, revogação e descadastro.
