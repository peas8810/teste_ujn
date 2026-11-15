# Brain UJN — Identificação de artigo a partir de DOCX/PDF (15/11/2026)

## Objetivo
Ao abrir um e-mail, a Central deve procurar título, ID de submissão, DOI e URL nos arquivos anexados e, quando possível, consultar OJS somente para confirmar **artigos publicados**. Nenhum vínculo é criado automaticamente.

## Estado implantado em GitHub e Supabase
- `integracoes/webmail/ujn_email_mime_adapter.py`: extrai texto DOCX (incluindo hiperlinks externos nas relações do ZIP), TXT e PDFs com texto selecionável se `pdftotext` estiver disponível no servidor. Sem OCR.
- `integracoes/webmail/ujn_email_mime_recover_recent.py`: ganhou `--reindex` com checkpoint próprio para reprocessar até 300 UIDs recentes por pasta, sem tocar o checkpoint da sincronização principal.
- `public.ujn_email_desk_attachments`: colunas privadas `extracted_text`, `extraction_status`, `extracted_at`.
- `ujn-email-attachment-ingest` v3: recebe e salva até 16000 caracteres de texto extraído com o anexo no bucket privado.
- `ujn-email-desk-v1` v30: `analyze` considera a evidência do anexo, identifica candidatos e tenta confirmar publicação no OJS usando ID ou título; o texto integral do documento **não** é devolvido ao frontend.
- `ujn-ojs-public-lookup` v5: busca somente publicações com status de publicado, aceitando título; não conclui que remetente é o autor.
- `brain/index.html`: mostra um painel visível abaixo das mensagens, com título, IDs, DOI, URLs, publicação localizada e indicação de verificação.

## Instalação no cPanel
Pasta: `/home/ujn/brain-ujn/`

1. Substituir **somente** `ujn_email_mime_adapter.py` e `ujn_email_mime_recover_recent.py` pelos novos arquivos do GitHub; não é necessário alterar os outros scripts.
2. Verificar sintaxe pelo Terminal ou Cron temporário:
```bash
/usr/bin/python3 -m py_compile /home/ujn/brain-ujn/ujn_email_mime_adapter.py /home/ujn/brain-ujn/ujn_email_mime_recover_recent.py
```
3. O Cron IMAP permanente já contém `UJN_IMAP_MIME_ENABLED=1 UJN_IMAP_ATTACHMENTS_ENABLED=1`. **Não alterar** quatro Cron permanentes.
4. Arquivos novos serão analisados quando recebidos normalmente. Para atualizar **anexos já armazenados**, como DOCX que abriu pelo Brain, executar recuperação única e curta:
```bash
UJN_IMAP_MIME_ENABLED=1 UJN_IMAP_ATTACHMENTS_ENABLED=1 timeout 110s /usr/bin/python3 /home/ujn/brain-ujn/ujn_email_mime_recover_recent.py --reindex --limit 10
```
Sem Terminal, criar um quinto Cron temporário de uma execução (com flag e lock) e depois excluí-lo, preservando os quatro permanentes. Em caso de erro, não reexecutar em massa.
5. No Brain UJN, abrir uma conversa com DOCX, aguardar a análise e verificar `IA — identificação do artigo pelo anexo`.

## Interpretação dos resultados
- ID encontrado no documento ≠ ID verificado no OJS.
- URL/DOI encontrado é uma referência no documento, não confirmação de publicação.
- Se o ID/título e a revista forem suficientes e a API OJS retornar a publicação, mostrar o link como **publicação identificada no OJS**.
- A condição de autor e o vínculo com a conversa exigem conferência humana; não criar automaticamente `ujn_email_desk_article_links`.
- Documentos antigos continuam sem texto até nova captura/reindexação.
- PDFs digitalizados e imagens não têm OCR; `pdftotext` é opcional e precisa existir no cPanel. Arquivos grandes, protegidos ou corrompidos podem permanecer sem texto.
- O texto extraído permanece privativo no backend e pode ser usado pela IA da análise; acesso de operadores continua autenticado.

## SQL de auditoria
```sql
select availability, extraction_status,count(*) from public.ujn_email_desk_attachments group by availability,extraction_status;
select count(*) filter(where extracted_text is not null) as documentos_lidos from public.ujn_email_desk_attachments;
```
