# Brain UJN Mobile — PWA (17/11/2026)

## Escopo implantado
- Mesma aplicação web em `brain/index.html`, sem aplicativo separado e sem publicação em loja.
- `brain/manifest.webmanifest` com escopo relativo ao GitHub Pages e atalhos para E-mails, WhatsApp e Início.
- `brain/sw.js` com navegação online e fallback genérico em falta de conexão.
- Ícones de 192 e 512 pixels, SVG e suporte de ícone iOS.
- Barra inferior responsiva de cinco atalhos: Início, E-mails, WhatsApp, Alertas e Mais.
- Ajustes para leitura e respostas de e-mail, telas estreitas e áreas seguras do sistema.

## Endereço
https://peas8810.github.io/teste_ujn/brain/

## Instalação sem loja
- iOS: abrir no Safari, Compartilhar → Adicionar à Tela de Início.
- Android: abrir no Chrome, menu ⋮ → Instalar aplicativo (ou Adicionar à tela inicial).

## Segurança
- Nenhuma mensagem é enviada automaticamente pela instalação.
- Auth e controles de permissão continuam nos serviços existentes.
- Nenhum dado de autor, token, resposta de API ou anexo é guardado em cache pelo service worker.
- O service worker consulta a rede para navegação e oferece apenas um aviso genérico quando offline.
- Sem push notifications nesta primeira versão.

## Homologação manual necessária
1. Confirmar que o manifesto e ícones estão sendo servidos por HTTPS.
2. Instalar no Safari iOS e no Chrome Android, verificar abertura standalone.
3. Entrar com a conta de operador e sair, verificar isolamento da sessão.
4. Testar leitura de e-mails e abertura de anexo; testar editor e fila SMTP com uma mensagem autorizada de teste.
5. Testar WhatsApp, Alertas e menu Mais em tela 375–430 px.
6. Testar sem rede: deve exibir mensagem de conexão, nunca conteúdo privado armazenado.
7. Reabrir após nova versão publicada; sem cache de HTML de usuário.

## Limitações
O código foi publicado e revisado no repositório. A instalação em dispositivos físicos e a distribuição efetiva pelo GitHub Pages exigem verificação na URL e no navegador após a publicação.
