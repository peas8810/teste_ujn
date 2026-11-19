# Brain UJN — Respostas antecipadas por IA (implantação 19/11/2026)

## Objetivo
Preparar **rascunhos** de e-mail antes da abertura da conversa pelo operador; análise e envio continuam sob **revisão e autorização humana**. Sem envios automáticos de IA.

## Componentes ativos
- `public.ujn_email_auto_prep_jobs`: fila privada por mensagem recebida, status QUEUED / RUNNING / READY / REVIEW / NO_REPLY / HUMAN_DRAFT / SUPERSEDED / COMPLETED / FAILED.
- Trigger `trg_ujn_email_auto_prep_on_inbound`: só enfileira nova mensagem recebida na caixa `contato@ujn.ojsbr.com`, sem reprocessar importações antigas ou duplicatas e sem tocar no cursor IMAP.
- Trigger `trg_ujn_email_auto_prep_outbound_complete`: marca resposta preparada como concluída depois que uma mensagem enviada for efetivamente registrada.
- RPC privadas `ujn_email_auto_prep_claim` e `ujn_email_auto_prep_finish`: claim transacional com SKIP LOCKED, três tentativas, verificação de última mensagem recebida, sem sobrescrever rascunho humano.
- Edge Function `ujn-email-auto-prep`: endpoint interno autenticado por `x-ujn-editorial-internal` (segredo já existente via `ujn_lab_internal_poll_secret()`). Recupera mensagens do mesmo fio, eventos editoriais verificados, pares aprovados `ujn_email_desk_training_examples` e precedentes de respostas humanas, usando o mesmo modelo configurado para a IA editorial. Classifica notificações como NO_REPLY.
- pg_cron `ujn-email-auto-prep-1m` (jobid 12): uma execução por minuto via pg_net. Não adiciona Cron no cPanel.
- Edge `ujn-email-desk-v1` ações `list`, `thread` e `auto_prep_stats`: estados, rascunhos e métricas apenas para operadores autenticados.
- `brain/index.html`: etiquetas de situação na caixa de entrada, filtro **IA pronta**, indicador de preparo por sete dias, visualização resumida, rascunho aberto automaticamente e botão para ir ao editor.

## Caminho do processamento
1. O IMAP existente importa a mensagem normalmente.
2. O trigger só enfileira a mensagem recebida elegível (independentemente do êxito da IA).
3. Executor separado reivindica um trabalho atomicamente e aplica classificação.
4. Se for informativa, define NO_REPLY sem criar rascunho.
5. Se requer resposta, recupera políticas verificáveis, histórico do mesmo fio, exemplos aprovados de respostas e contexto editorial vinculado.
6. Salva sugestão no repositório atual de rascunhos somente quando não há outro rascunho DRAFT. Guarda texto original e evidências no `source_snapshot`.
7. Ao abrir a conversa, o operador encontra a resposta pronta, pode editar/reescrever e autorizar pelo processo SMTP já existente.
8. Só após envio efetivamente registrado a captura supervisionada existente poderá usar a resposta humana final como exemplo.
9. Nova mensagem invalida a proposta antiga; preserva rascunhos com edição humana. As duas funções de aprovação existentes verificam o ID da última mensagem quando o rascunho surgiu de preparação automática.

## Comportamento de segurança
- **Nenhuma** ação deste projeto chama o SMTP, `approve_send`, envio WhatsApp ou marketing.
- Não altera Cron, coleta IMAP, cursor de leitura ou regras de consentimento.
- Não é permitido reaproveitar eventos ou respostas de outros autores como prova do caso atual.
- `READY` significa *pronta para revisão*, não aprovação de publicação, parecer editorial ou autorização de envio.
- `REVIEW` obriga análise criteriosa de fatos/risco. `NO_REPLY` não exclui o e-mail, apenas dispensa minuta automática.
- Dados de fila com RLS ativada; execute das funções sensíveis apenas pelo `service_role`.
- Em falha de IA, o trabalho entra em nova tentativa limitada ou `FAILED`. O IMAP continua.
- O gerador manual e reescrita com IA continuam disponíveis como alternativa.
- Segredos não são enviados ao frontend e nenhum conteúdo privado é armazenado em cache para uso offline.

## Verificação executada
- Trigger e tabelas criados no banco ativo; Cron presente e rodando.
- Foram criados trabalhos iniciais em lote controlado para conversas recentes.
- Uma notificação editorial resultou em NO_REPLY sem criação de rascunho; um caso financeiro resultou em REVIEW com rascunho verdadeiro e texto original da IA guardado.
- Rascunhos humanos preservados por salvamento condicionado no banco.
- Sintaxe JavaScript do portal verificada antes do envio ao GitHub.
- **Homologação visual, revisões humanas e envio de mensagem de teste ainda dependem do navegador do usuário.**

## Operação
No Brain UJN: **E-mails → Caixa de entrada → IA pronta**. Os estados exibem preparado, revisão, em fila ou informativo. Selecione um item pronto para abrir automaticamente o editor com texto já preparado. Confira artigo, assunto, destinatário e fatos antes de clicar em **Autorizar e colocar na fila de envio**.

## Monitoramento
```sql
select status,count(*) from public.ujn_email_auto_prep_jobs group by status;
select jobid,jobname,schedule,active from cron.job where jobname='ujn-email-auto-prep-1m';
select status,category,attempts,completed_at from public.ujn_email_auto_prep_jobs order by created_at desc limit 20;
```
Critérios de expansão: taxa de aproveitamento, edições, precisão factual, casos NO_REPLY, falhas, latência de processamento e custo por resposta. Não utilizar acerto automático para autorizar e-mails sem revisão.

## Desativação emergencial sem perda de dados
Desabilitar SOMENTE o agendamento `ujn-email-auto-prep-1m` em pg_cron; o coletor IMAP e SMTP permanecem independentes. Não remover rascunhos ou UIDs IMAP.
