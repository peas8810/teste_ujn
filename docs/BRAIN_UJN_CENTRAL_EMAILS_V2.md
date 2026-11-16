# Brain UJN — Central de E-mails 2.0 (15/11/2026)

## Objetivos entregues
Ampliação do módulo **E-mails · IA e envios**, sem modificar os scripts Cron existentes do cPanel.

### Navegação e operações
- **Entrada:** até 300 conversas ativas (state AWAITING_REPLY, MANUAL_REVIEW, UNTRIAGED).
- **Enviados:** conversas com mensagens OUTBOUND registradas, a partir da pasta IMAP Sent e dos envios supervisionados.
- **Rascunhos:** conversas com rascunhos de estado DRAFT.
- **Arquivados:** conversas em ARCHIVED e não excluídas.
- **Lixeira:** exclusão **lógica** por deleted_at, preservando e-mails, anexos e trilha de auditoria. A restauração recupera o estado anterior. Não move/apaga e-mails do Roundcube/cPanel.
- **Respondidas:** conversas ANSWERED, além dos filtros por leitura/não leitura.
- Seleção individual e múltipla, seleção dos itens visíveis no filtro, marcar lida/não lida e arquivar/excluir/restaurar.
- Marcações de leitura são por operador **no Brain UJN**, não alteram a flag Seen do Webmail.
- Exclusão cancela solicitações QUEUED/PENDING_ACTIVATION da conversa e o SMTP verifica lixeira antes de despachar. Envios já CLAIMED podem exigir conciliação.
- Contatos salvos em `ujn_email_desk_contacts`; cadastro manual com nome, e-mail, revista e observações. RLS sem políticas públicas, acesso via Edge Function autenticada.
- Encaminhar requer contato previamente salvo, revisão do assunto e corpo, confirmação do operador e fila SMTP supervisionada. **Somente texto; anexos não são encaminhados.** O RPC específico registra `send_kind=FORWARD` e não finge ser resposta ao autor.

### Dashboard — histórico total importado
A aba estatística consulta `ujn_email_desk_statistics()` (SQL agregado de acesso somente service role), não apenas a página de 300 conversas.
- Mensagens recebidas/enviadas; número de conversas; pendências; arquivadas; lixeira; rascunhos.
- Remetentes recorrentes: favorece `Reply-To` verificado e ignora endereços técnicos do OJS quando não é possível atribuir o autor.
- Categorias recorrentes nos assuntos: submissões, pares, pagamento, publicação/DOI, correções, outros.
- Palavras nos títulos e no texto recebido, ignorando termos genéricos comuns.
- Títulos científicos possivelmente mencionados nos assuntos de notificação; áreas científicas **inferidas por palavras-chave, não confirmadas pelo OJS**.
- Volume por mês e tempo aproximado entre última entrada e última saída de conversas comparáveis.
- Todos os números são do **acervo sincronizado no Supabase**, não necessariamente das 16 mil mensagens existentes no servidor.

### IA supervisionada e histórico
- `ujn_email_desk_reply_examples` registra somente resposta **aprovada e confirmada SENT**, jamais rascunhos não enviados.
- Respostas anteriores de dois envios com destinatário validado foram incorporadas inicialmente; um envio antigo para endereço técnico incorreto foi excluído do material de referência.
- `ujn_email_desk_author_history(thread_id)` recupera mensagens **de outras conversas do mesmo autor**, associado por `Reply-To` ou `From` devidamente verificado.
- O gerador de respostas usa estilo de exemplos semelhantes, últimos e-mails da conversa, histórico verificado do próprio autor, assuntos de respostas anteriores e eventos OJS existentes. O material histórico é contextual; não autoriza decisões, mudanças de status ou disparos.
- **Não se trata de fine-tuning de pesos de modelo.** Trata-se de recuperação contextual incremental (RAG) e memória auditável, deliberadamente restrita a envios efetivamente supervisionados.
- Proteções anteriores de `Reply-To`, aprovação explícita, SMTP com reconciliação e vínculo multiartigos continuam.

### Componentes modificados
- Supabase `ujn-email-desk-v1` v40: listagens por pasta, operações em lote, agenda, encaminhamentos, dashboard, recuperação de exemplos e histórico do autor.
- Banco: `ujn_email_desk_threads.deleted_at/pre_delete_state`, `ujn_email_desk_contacts`, `ujn_email_desk_reply_examples`, `ujn_email_desk_send_queue.send_kind`; RPCs restritos a service role.
- Frontend: `brain/index.html` no GitHub Pages; botão **Dashboard estatístico** e pastas da Caixa postal.

### Implantação e aceitação
- Não é necessário alterar **nenhum Cron do cPanel**. Códigos do painel no GitHub e recursos do backend no Supabase já foram publicados.
- Auditoria técnica feita: migrações SQL aplicadas, funções Edge publicadas, JavaScript do painel validado sintaticamente e função agregada executada com dados reais.
- Testes de interação de ponta a ponta com sessão do operador ainda necessários: carregar abas, marcar leitura, arquivar/restaurar, salvar contato, abrir formulário de encaminhamento e gerar resposta da IA. **Não encaminhar conteúdo real apenas para teste**.
- Atualizar a página com Ctrl+F5 para obter a versão recente do GitHub Pages. Recomenda-se conferir o último commit da branch main se aparecer código em cache.

### Segurança e limites
- Não existe envio autônomo pela IA.
- Lixeira é reversível e não altera IMAP; exclusões permanentes não foram implementadas.
- Encaminhamento usa apenas texto; anexo deverá ser fornecido manualmente por fluxo seguro se necessário.
- Fontes históricas podem estar incompletas por causa do limite de importação das últimas 300 UIDs por pasta.
- Tópicos e termos são heurísticos; permitem priorizar estudos de carga editorial, não representam diagnósticos científicos validados.
