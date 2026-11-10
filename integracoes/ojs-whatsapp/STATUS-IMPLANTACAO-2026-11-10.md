# Brain UJN — Validação e conclusão da integração editorial
Data: 2026-11-10

## Resultado da auditoria de produção
- IMAP `mail.ujn.ojsbr.com:993`: autenticação e leitura da caixa confirmadas, Python 3.6.8 e Cron a cada 5 minutos.
- `imap_monitor.py`: atualizado com diagnósticos agregados de motivo de exclusão e contagens por revista. NÃO envia WhatsApp e NÃO chama o Supabase.
- APIs OJS cadastradas no Supabase em `verified_readonly`: REMUNOM, RJNM, RSV, JIRRS e NEXUS. Isso não prova que todos os eventos editoriais ou telefones estejam disponíveis nos endpoints.
- Funções Supabase existentes: `ujn-editorial-email-ingest`, `ujn-editorial-wa-poll`, `ujn-editorial-wa-dispatch`, `ujn-editorial-wa-optout`.
- `ujn_editorial_email_sources`: 5 fontes **desativadas**, remetentes permitidos vazios.
- `ujn_editorial_wa_recipients`: **0** contatos habilitados/validados.
- `ujn_editorial_wa_settings.delivery_enabled`: **false**.
- `ujn_editorial_email_intake`, `ujn_editorial_wa_deliveries`: **0** linhas.
- Não há comprovação de que e-mails enviados diretamente aos autores também cheguem à caixa `contato@ujn.ojsbr.com`.

## O que permanece operando
1. Manter exatamente **uma** tarefa Cron `*/5 * * * *` executando `imap_monitor.py`.
2. Não excluir `/home/ujn/brain-ujn/state/` nem o banco SQLite, que conserva a baseline IMAP.
3. O relatório `state/monitor-status.json` mostra `reasons` e `journals` por ciclo. Um ciclo sem novas mensagens naturalmente tem contadores zerados; não implica falha.
4. Não criar tarefa de envio ou ativar `delivery_enabled` apenas para testar.

## Fluxo-alvo (com dados autorizados)
```
OJS (cinco revistas, leitura autorizada) / notificações SMTP copiadas legitimamente
 -> monitor de eventos e deduplicação por revista + submissão + evento
 -> correspondência verificável autor e telefone + prova de opt-in
 -> minuta PENDING_APPROVAL
 -> aprovação operacional READY
 -> dispatcher com trava de envio + template WhatsApp aprovado
 -> recibo do provedor, auditoria, opt-out
```

## Pontos que exigem dados/ações externas — não é seguro inferi-los
1. **Cobertura real de eventos**: uma conta IMAP que recebe mensagens ao editor não copia automaticamente mensagens dirigidas aos autores. Homologar evento por revista ou disponibilizar acesso OJS autorizado a submissões e movimentações, com políticas de acesso.
2. **Destinatários**: obter telefone fornecido voluntariamente, ID OJS, e-mail da autoria, consentimento específico para WhatsApp, registro da prova e mecanismo de revogação. Não expor autores em análise a qualquer pessoa por nome ou DOI.
3. **Meta**: verificar o template utilitário aprovado, os campos permitidos, a janela de conversa e o número UJN antes de qualquer disparo real.
4. **Credenciais de ingestão**: a função HMAC precisa de segredo configurado no servidor; jamais colocar segredo ou senha em GitHub, log ou no chat.
5. **Homologação ponta a ponta**: um autor-teste consentido em cada revista; eventos de submissão, revisão, mensagem, decisão, produção e publicação; confirmar duplicidade zero e log de entrega/erro.

## Critérios objetivos de aceitação
- Cinco revistas: conectores efetivamente conseguem consultar ao menos uma submissão de teste por revista, inclusive inédita, com permissão explícita.
- Um evento novo não gera mais que uma minuta para a mesma pessoa e submissão.
- Zero notificações a editor, revisor não destinatário, ou terceiros com telefone não validado.
- Primeiro contato apenas após opt-in específico; texto do WhatsApp não contém parecer, conversa privada, token ou link administrativo.
- Recebimento de status do gateway Meta e opt-out testado, com a fila em modo bloqueado antes da homologação.
- Auditoria por revista, evento, resultado, data e status; nenhuma credencial nos logs.

**Situação honesta:** monitor e infraestrutura preparados; sistema de envios reais NÃO está concluído até que as dependências externas acima estejam preenchidas e testadas.


## Atualização operacional posterior — 10/11/2026

As informações anteriores acima descrevem o estado observado **antes** desta atualização. O estado mais recente, confirmado por consultas SQL, é:
- Editora UJN: `ujn_channels.template_name = ujn_editorial_update_ptbr`; `enabled=true`; telefone Meta configurado. O template ainda estava **Em análise** na última captura do usuário.
- Cinco fontes `ujn_editorial_email_sources` habilitadas com o remetente autorizado `ujn@journals.ojsbr.com`; HMAC segue obrigatório.
- A migração `ujn_editorial_wa_verified_has_evidence` passou a exigir prova de consentimento, origem e hash do e-mail para qualquer destinatário marcado como verificado.
- O `imap_monitor.py` mais recente dispõe de fila SQLite para UIDs elegíveis (`pending_mail`) e encaminhamento assinado para a função `ujn-editorial-email-ingest`, **somente** após configuração local de `ingest_config.json` com HMAC válido (permissão 600). Sem a chave, os UIDs ficam pendentes e nenhum conteúdo é transmitido.
- A tarefa Cron da hospedagem continua apontando para o arquivo local; **publicar no GitHub não atualiza automaticamente a cópia no cPanel**.
- Consulte [ATIVAR-PONTE-IMAP-SUPABASE.md](ATIVAR-PONTE-IMAP-SUPABASE.md) para as instruções seguras de instalação e [ingest_config.example.json](ingest_config.example.json) para o formato sem segredo.
- Última verificação: `recipients=0`, `intake=0`, `ready=0`, `sent=0`. Logo ainda não é possível afirmar envio real nem homologação integral.
