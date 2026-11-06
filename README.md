# Editora UJN — Portal de Gestão (LAB)

Frontend de homologação separado da produção. Publicado no GitHub, branch `main`, arquivo `index.html`.

## Hospedagem estática
O Supabase Edge Functions **não serve HTML** em domínios compartilhados: devolve `text/plain`. Use GitHub Pages ou outra hospedagem estática.

Para habilitar GitHub Pages neste repositório de testes:
1. Acesse `https://github.com/peas8810/teste_ujn/settings/pages`
2. Em **Build and deployment**, selecione **Deploy from a branch**.
3. Selecione `main` e a pasta `/(root)`; salve.
4. Aguarde a URL aparecer no próprio GitHub Pages e abra a página no navegador.
5. URL esperada *somente após confirmação de publicação*: `https://peas8810.github.io/teste_ujn/`.

## Módulos de navegação
- Início: navegação unificada, interface institucional.
- Submissão: revista → mensagem WhatsApp manual; alternativa ArticleRun.
- Acompanhamento: contato WhatsApp com referência; consulta OJS ainda pendente.
- Academy: área informativa, sem emissão comercial.
- ArticleGenius: conferência local básica, sem IA externa.
- Atendimento: abre WhatsApp, não recebe automaticamente.
- Administração: resumo de infraestrutura; não há cadastro público de chaves.

## Backend existente, ambiente separado de produção
Projeto Supabase LAB: `leytqsyfrmzhectatcqm`.
Edge Functions: `ujn-public-submission-lab`, `ujn-lab-console`, `ujn-ojs-lab-settings`, `ujn-whatsapp-lab-webhook`, `article-run-proxy`.
**Não utilizar o link da Edge Function como link do site**, pois devolve HTML como texto.

## Bloqueios para MVP real
- Validar e instalar novas credenciais individualizadas dos cinco OJS no servidor, nunca no frontend.
- Validar ações de criação de rascunho, metadados, arquivos e submissão em ambiente seguro.
- Rotacionar credenciais OJS já expostas no chat.
- Configurar Turnstile (site key + secret), armazenamento privado, antimalware, limites e política de privacidade antes de receber arquivos reais.
- Validar o webhook real da Meta, número e remetentes autorizados, assinaturas, mídias e roteamento sem mudar o existente.
- Criar autenticação de autor/validação de identidade no acompanhamento e consentimento antes da submissão.
- Implementar integralmente e homologar Academy, ArticleGenius/IA, cobranças, QR e revogação.

É proibido considerar um identificador LAB como prova de envio ao OJS. Nenhum módulo deve enviar submissões reais, cobrança ou mensagens externas sem aprovação específica de produção.
