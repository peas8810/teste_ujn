# Brain UJN — Aprendizado supervisionado das respostas de e-mail
Data: 16/11/2026.

## Motivação
Operadores consideram as respostas geradas pela IA excessivamente genéricas. A nova capacidade agrega exemplos fidedignos de **e-mail recebido + resposta final revisada e enviada**, com controles de ativação, revisão e exclusão.

## Fluxo operacional
1. Na página **E-mails · IA e envios** aparece o cartão `Aprendizado supervisionado da IA`. Cada operador tem botão `Ativar aprendizado` e pode `Desativar aprendizado`.
2. A opção começa **desativada** para todas as pessoas, até clique com confirmação no Brain. Preferência fica em `ujn_email_desk_training_settings` por operador.
3. Quando a IA gera um rascunho, `ujn_email_desk_drafts.original_ai_text` preserva a versão bruta. O operador pode editar texto ou redigir manualmente; o editor normal continua funcionando.
4. O envio segue o SMTP supervisionado com conferência de `Reply-To`, aprovação humana, proteção de não duplicação e sincronização com Roundcube.
5. **Somente depois do status `SENT`**, o trigger do Supabase associa a última mensagem recebida antes da aprovação com o texto final enviado e a sugestão original, se houver.
6. Com modo `EDITED_SENT` ativo, rascunho gerado sem alteração não vira exemplo; texto manual criado por operador também pode virar exemplo.
7. `ujn_email_desk_training_pairs` armazena `request_id` exclusivo, `inbound_message_id`, assunto, texto original recebido (até 19 mil caracteres), resposta inicial da IA, texto final enviado, operador, revista e estado de qualidade.
8. `Revisar exemplos` lista registros do operador e `Não usar como exemplo` altera o estado para `EXCLUDED`. Nenhuma dessas operações apaga o e-mail original.
9. `generate` busca até cinco exemplos aprovados de maior semelhança textual com mensagem atual via função PostgreSQL `ujn_email_desk_training_examples`; usa a revista como reforço de pontuação. Exemplos são tratados como dados de estilo/procedimento, não como evidência sobre outro autor.
10. O histórico anterior `ujn_email_desk_reply_examples` continua sendo consultado; a nova fonte de pares editados é adicional, sem destruir registros já existentes.

## Escopo e segurança
- Toda mensagem IMAP recebida continua arquivada na tabela `ujn_email_desk_messages` independentemente da opção; **o que depende do opt-in é usá-la junto da resposta enviada como exemplo de melhoria da IA**.
- Operador tem controle por sessão/identidade sobre novos exemplos. Pareamentos ficam em tabelas privadas com RLS habilitada, sem políticas públicas; a Edge Function verifica a sessão.
- O texto bruto pode conter dados pessoais. A base é interna, não é transferida automaticamente para treinamento de pesos do modelo. Na geração, os exemplos de outras conversas são parcialmente redigidos para remover e-mails, telefones e URLs e não devem ser interpretados como instruções.
- Não inclua em mensagens futuras detalhes, decisões, valores, número de manuscrito ou dados pessoais extraídos de outros autores.
- O usuário pode **desativar futuras capturas** e **excluir da recuperação** os exemplos antigos por botão de revisão, sem apagar logs SMTP.
- A retenção e eventual exportação/eliminação definitiva devem seguir política de proteção de dados da editora; o botão de exclusão apenas remove exemplos de futuras consultas, não apaga os pares do banco.
- Aprendizado aqui significa **RAG / memória supervisionada**, não fine-tuning dos pesos de um modelo.
- As funções de consulta/captura foram testadas na camada SQL e a Edge Function foi implantada; **teste funcional ponta a ponta com envio real e sessão autenticada ainda não realizado**. Não enviar mensagens apenas para testar.

## Como ativar
1. Abrir [Brain UJN](https://peas8810.github.io/teste_ujn/brain/) e pressionar Ctrl+F5.
2. Entrar em `E-mails · IA e envios`.
3. Clicar `Ativar aprendizado` e confirmar.
4. Em uma mensagem real: `Gerar resposta com IA`, revisar/editar, aprovar e aguardar `SENT`.
5. Clicar `Revisar exemplos` para conferir o novo registro e excluir exemplos inadequados.
6. A geração posterior usa o histórico aprovado de forma contextual, junto ao histórico do próprio autor, OJS e demais proteções.

## Arquivos modificados
- Supabase migrações `ujn_desk_optin_edited_reply_learning`, `ujn_desk_training_or_lexical_retrieval_improved`.
- Edge Function `ujn-email-desk-v1`, versão 42.
- GitHub `brain/index.html`.

**Nenhuma alteração necessária nos quatro Cron IMAP/SMTP nem no sincronizador de flags Roundcube.**
