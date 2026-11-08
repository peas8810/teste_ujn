# Brain UJN — Estado técnico e critérios de liberação
Atualizado: 2026-11-07 (America/Sao_Paulo)

## Arquitetura
- Meta WhatsApp oficial usa o Supabase Academy; preservar o webhook de produção.
- OJS: cinco revistas com credenciais criptografadas e leitura homologada no LAB.
- ArticleRun: link externo de submissão; nenhum conector UJN escreve manuscritos no OJS.
- Academy: www.protocolo.me/academy/; pagamentos e emissão comerciais permanecem desligados.

## Recursos implantados
- Editor de menu e respostas por serviço, controle de superadministrador.
- Painel de conversas e monitor de filas de WhatsApp, notificações Academy e e-mail.
- Consulta administrativa de status por revista e número de submissão OJS.
- Portal de acompanhamento com solicitação de vínculo por autor; administrador precisa verificar autoria antes do acesso privado.
- Cron LAB a cada 15 minutos: consulta apenas vínculos verificados, detecta mudanças, cria rascunhos sem envio.
- Checklist de dez testes Academy com registro de evidência e bloqueio de PASS quando falta fato essencial.
- Validação pública de certificados ajustada para também rejeitar certificados revogados pela data de revogação.

## Evidências disponíveis
- Cinco conectores OJS: verified_readonly.
- Fila central WhatsApp: 15 mensagens em SENT na auditoria; não prova notificações Academy.
- Academy: quatro solicitações e um documento; sem aprovações, pagamentos, certificados ou notificações nesse ciclo.
- Etapa 4 LAB: 7 PENDING; 3 BLOCKED; 0 PASS.
- Commercial ready: false.
- No cofre de provedores Academy: pagamento e emissão desabilitados; credenciais essenciais não configuradas ali.
- Cron editorial interno testado e respondeu HTTP 200; não existem ainda vínculos verificados para consultar.
- Interfaces passaram por validação sintática de JavaScript, mas não por teste funcional autenticado completo.

## Pendências para conclusão
1. Configurar Mercado Pago sandbox no cofre Academy; testar checkout e webhook assinado.
2. Configurar segredo de assinatura e emissão sandbox; completar pedido fictício com aprovação documentada.
3. Homologar PDF, QR, validação pública e revogação de certificado fictício.
4. Configurar provedores Academy de e-mail e WhatsApp, consentimentos, templates e agendamento.
5. Realizar dez testes ponta a ponta e guardar evidências; não ativar comercial antes disso.
6. Vincular autor de teste comprovado a submissão OJS e testar mudanças editoriais.
7. Notificações editoriais automáticas por WhatsApp não habilitadas: rascunhos apenas no LAB.

## URLs
- https://peas8810.github.io/teste_ujn/
- https://peas8810.github.io/teste_ujn/gestao/
- https://peas8810.github.io/teste_ujn/acompanhamento/
- https://www.protocolo.me/academy/
- https://www.articlerun.org/submeter
