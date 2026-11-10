# Ativação da ponte IMAP → Supabase (sem esperar aprovação Meta)

## Já preparado no backend (10/11/2026)
- Modelo `ujn_editorial_update_ptbr` associado ao canal habilitado da Editora UJN, cujo identificador telefônico já está cadastrado. Meta ainda **Em análise**; não confirma aprovação.
- Fontes `ujn_editorial_email_sources` habilitadas para REMUNOM, RJNM, RSV, NEXUS e JIRRS; remetente aceito `ujn@journals.ojsbr.com`, assinatura HMAC obrigatória.
- Tabela `ujn_editorial_wa_recipients`: agora exige, para `verified_at` não nulo, `consent_at`, `consent_source`, `consent_evidence_ref` e `author_email_hash`. Nunca preencher consentimentos automaticamente sem prova.
- `delivery_enabled=true` é configuração global, **não** autorização para destinar mensagens a pessoas ainda não verificadas.
- O monitor `imap_monitor.py` mantém a baseline e, ao identificar e-mails aptos, insere somente UID em uma fila local SQLite. Sem chave HMAC, preserva os candidatos para futuro envio ao Supabase, sem salvar assunto/corpo.

## ÚNICA ação local para efetivar a ponte
1. No cPanel, **substituir apenas** `/home/ujn/brain-ujn/imap_monitor.py` pela última versão do GitHub. Não excluir `/home/ujn/brain-ujn/state/brain-ujn-imap.sqlite`, não reconfigurar o Cron existente.
2. No painel de produção do Supabase, projeto `leytqsyfrmzhectatcqm`, abrir SQL Editor (acesso restrito ao administrador) e obter localmente a chave já existente, sem enviar chave/screenshot ao ChatGPT:
   ```sql
   select public.ujn_editorial_email_ingest_key() as hmac_key;
   ```
3. Somente no Gerenciador de Arquivos cPanel, criar `/home/ujn/brain-ujn/ingest_config.json` preenchido com o valor da consulta:
   ```json
   {"hmac_key": "COLE_AQUI_O_VALOR_DA_CONSULTA"}
   ```
4. Alterar permissões do arquivo `ingest_config.json` para **600** (Usuário: ler/gravar; Grupo e Mundo: nenhum). **Não carregar nem fazer commit desse arquivo no GitHub.** O `imap_config.json` anterior deve permanecer 600.
5. Não alterar o Cron, já configurado para executar `imap_monitor.py` a cada cinco minutos.
6. Conferir `/home/ujn/brain-ujn/state/monitor-status.json`:
   - `ingest_configured: true`: chave detectada;
   - `ingest_queued`: quantidade de novas notificações candidatas reconhecidas neste ciclo;
   - `ingest_ok`: eventos entregues e aceitos pelo Supabase neste ciclo;
   - `ingest_failed`: eventos com falha, mantidos na fila para nova tentativa;
   - `pending_backlog`: eventos à espera de ingestão;
   - `reasons`: motivos agregados de descartes.
   
   Se não houver mensagens novas, `ingest_ok:0` é normal. Sem chave, `ingest_configured:false` e o monitor continua seguro.

## Limites e controle
- O monitor não altera, apaga ou marca e-mails como lidos. Só processa mensagens recebidas depois da baseline e que pareçam destinadas a um autor.
- A ingestão Supabase classifica e grava metadados mínimos; só cria evento/rascunho se existir vínculo inequívoco de autor verificado por revista + ID da submissão + hash do e-mail.
- Não criar telefones e aceites falsos. Não registrar 'consentimento validado' apenas pela autorização geral do proprietário.
- O gateway Meta pode rejeitar template ainda em análise. A aprovação e o teste com número do autor autorizado permanecem necessários para comprovar envio.
- A caixa institucional não é necessariamente cópia de mensagens aos autores; homologar cobertura real por revista e API OJS.
- Confirmar entrega com recibos Meta antes de afirmar 'WhatsApp enviado'.

## Teste simples sem WhatsApp
Depois de instalar a ponte, uma notificação real ao autor recebida na caixa institucional e classificada pelo monitor deve ser aceita por `ujn-editorial-email-ingest` e gerar `ujn_editorial_email_intake`. Se não houver correspondência no cadastro de autores, a classificação é `NEEDS_REVIEW`, sem geração de entrega.
