# Brain UJN — Conector Webmail (somente leitura)

**Configuração SSL/TLS confirmada no Webmail: IMAP `mail.ujn.ojsbr.com:993`; SMTP `mail.ujn.ojsbr.com:465`.** O SMTP está documentado apenas e permanece desativado.

**Caixa escolhida para a primeira integração: `contato@ujn.ojsbr.com`.** A conta está registrada como pendente de credenciais e a sincronização permanece desativada.

Este diretório contém o adaptador opcional para sincronização das pastas IMAP com a Central Inteligente de E-mails.

**Situação:** código publicado, **não instalado** no cPanel. O Supabase não consegue ler o servidor IMAP sem configuração da conta e execução do coletor.

## Integração existente

O Brain já possui um coletor de e-mails editoriais que envia **metadados** à função `ujn-editorial-email-ingest`. Não altere esse coletor em produção sem comparar as configurações existentes. Este adaptador destina-se à captura do histórico de conversas (mensagens recebidas e enviadas), lendo a chave HMAC do campo `hmac_key` já existente no arquivo privado `/home/ujn/brain-ujn/ingest_config.json`. Não executa ações no OJS nem envia e-mails.

## Instalação em ambiente privado

1. Coloque `ujn_imap_readonly_collector.py` em um diretório **fora** de `public_html`, por exemplo em uma pasta privada do usuário do cPanel.
2. Configure no ambiente do processo as variáveis abaixo. Nunca coloque valores reais no GitHub ou em arquivos públicos.
3. Valide o host IMAP, o endereço completo da conta e os nomes das pastas de enviados com o provedor (podem ser `Sent`, `INBOX.Sent` ou outros).
4. Execute primeiro manualmente para uma caixa de teste. Apenas após conferir os resultados, crie o cron sob o usuário que já opera as integrações do Brain.
5. Para evitar trabalhos IMAP duplicados, se o coletor atual já possui acesso ao conteúdo integral dos e-mails, prefira integrar a chamada HTTP assinada ao seu processo existente em vez de agendar o adaptador separadamente.

### Configuração de leitura — sem duplicar senhas

O adaptador já está configurado para ler a conta `contato@ujn.ojsbr.com` no servidor `mail.ujn.ojsbr.com:993`.

**Ele carrega automaticamente estes dois arquivos privados do cPanel:**
- `/home/ujn/brain-ujn/ingest_config.json`, campo `hmac_key` (assinatura HMAC).
- `/home/ujn/brain-ujn/imap_config.json`, para a senha IMAP já existente.

São reconhecidos nomes de campos usuais `password`, `senha`, `imap_password`, `mail_password` ou campos aninhados `imap.password`, `imap.senha`, `email.password`, `account.password` e `credentials.password`.

Se a senha estiver em um campo de outro nome, informe **somente o caminho do campo** (nunca a senha) através da variável opcional `UJN_IMAP_PASSWORD_FIELD`; exemplo: `UJN_IMAP_PASSWORD_FIELD=servidor.credencial`.

A URL de integração é `https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-email-desk-v1`.

Antes de executar pela primeira vez, valide a identificação da pasta `Sent` na conta; ela pode ter outro nome. A configuração opcional `UJN_IMAP_FOLDERS=INBOX,Sent` controla as pastas lidas.

**Instalação pendente:** baixe o arquivo Python atualizado para o diretório privado `/home/ujn/brain-ujn/` e execute manualmente em homologação, nunca a partir do GitHub Pages. Não crie cron até a validação do teste. Não altere os arquivos de configuração originais.

## Comportamento

- Lê por IMAP em modo `readonly` e utiliza `BODY.PEEK[]`, sem marcar e-mails como lidos.
- Limita a varredura por pasta e usa `Message-ID` para deduplicação.
- Envia apenas texto simples limitado; não transfere anexos.
- Recebidos entram como `INBOUND` e mensagens da pasta enviados como `OUTBOUND`.
- A identificação por `References`/`In-Reply-To` é aproximada. Conversas sem cabeçalhos adequados devem ser revisadas.
- O operador autorizado pode gerar uma sugestão, editar, marcar como aprovada para cópia e colar no Webmail.
- **Não há envio SMTP** nem botão de envio neste estágio.

## Privacidade e segurança

Confirme a base legal e a política de retenção de mensagens e anexos antes de sincronizar o histórico completo. As tabelas possuem RLS e não concedem acesso direto aos papéis `anon` e `authenticated`. A API valida o operador e o coletor utiliza autenticação HMAC com janela temporal.

## Critérios de homologação pendentes

- Testar login de operador e geração de rascunho com uma mensagem de caixa real autorizada.
- Validar reconhecimento de respostas na pasta Enviados do servidor.
- Verificar carga do cron, falhas de rede e deduplicação em duas leituras consecutivas.
- Validar retenção de mensagens e estratégia de remoção conforme a política da UJN.
- Testar configuração SMTP somente em fase posterior, com autorização humana e bloqueio de duplicidades.


## Envio supervisionado via SMTP — implantação

O script `ujn_smtp_supervised_worker.py` usa a **mesma configuração privada** do IMAP e a conexão segura SMTP de `contato@ujn.ojsbr.com` em `mail.ujn.ojsbr.com:465`.

**Comportamento atual:**
- O painel permite registrar autorização para um rascunho, com destinatário, assunto e texto revisados.
- Enquanto `smtp_enabled=false`, a solicitação fica `PENDING_ACTIVATION`, **não entra na fila executável** e não é enviada quando o SMTP for ativado posteriormente. Será preciso preparar uma nova autorização.
- O servidor de e-mail **não está conectado ao worker neste momento**. Não é possível acionar o cPanel a partir do GitHub ou diretamente da aplicação web.
- A fila só pode ser consumida por processo privado com assinatura HMAC do coletor, usando um único disparo `--send-one`, sem repetir tentativas com resultado incerto.

### Teste de autenticação SMTP sem transmitir mensagens

Copie `ujn_smtp_supervised_worker.py` para `/home/ujn/brain-ujn/`. No cPanel, crie **temporariamente** uma tarefa Cron a cada minuto contendo:

```sh
timeout 45s python3 /home/ujn/brain-ujn/ujn_smtp_supervised_worker.py --test-auth > /home/ujn/brain-ujn/state/teste_smtp_auth.log 2>&1
```

Exclua a tarefa após a primeira execução e abra o arquivo `/home/ujn/brain-ujn/state/teste_smtp_auth.log`. Saída esperada:

```json
{"smtp_authenticated": true, "sent_email": false, "host": "mail.ujn.ojsbr.com", "port": 465}
```

Esse comando **não envia e-mails**, mesmo com credenciais corretas. Se houver erro, envie somente o nome da exceção/descrição, nunca senha ou token.

### Antes de habilitar qualquer envio real

1. Confirme a autenticidade do remetente e as permissões da conta.
2. Homologue a pasta Enviados do IMAP para conciliar mensagens enviadas pelo painel e pelo Webmail.
3. Estabeleça uma política de retenção e uma confirmação explícita da conta para teste.
4. Não habilite `smtp_enabled` nem agende o worker `--send-one` antes de cumprir essas verificações.
5. O worker registra a mensagem enviada no banco apenas quando o servidor SMTP confirma aceitação; falhas de comunicação ficam como `UNKNOWN` sem reenvio automático.
6. Os envios são autorizados individualmente pelo operador. Nenhuma resposta da IA é enviada sem revisão.

### Instalação opcional após homologação (não executar agora)

O worker oferece `--send-one` para consumir **uma** solicitação `QUEUED` previamente aprovada, enviar pelo SMTP e atualizar o banco. O processo nunca deve ser executado automaticamente até o teste de ponta a ponta, confirmação de pasta Enviados e política de duplicidade.

