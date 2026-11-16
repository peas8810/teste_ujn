# BRAIN UJN — Plano e primeira implantação DevSecOps (16/11/2026)

## Contexto real da aplicação
- Painel HTML/JavaScript no GitHub Pages `/brain/`; não é Node.js nem Django.
- API editorial: Supabase Edge Functions Deno/TypeScript, incluindo `ujn-email-desk-v1`.
- PostgreSQL Supabase com service_role usado exclusivamente nas Edge Functions e nos executores privados.
- Identidade do painel utiliza Supabase Auth do **Academy** (ou conta operador UJN), com validação cruzada e RBAC em `ujn_lab_operators`.
- Rotinas Python 3.6 no cPanel para IMAP, SMTP, flags de Webmail; WhatsApp Meta e Academy são integrações distintas.
- O painel usa JWT Bearer **em memória da aba** e não autenticação por cookies do próprio site. Não existe HttpOnly viável no GitHub Pages estático para armazenar os tokens da aplicação sem criar um backend/BFF de sessão. Evitar uma migração de sessão no mesmo deploy da correção de e-mail.

## Auditoria e risco
1. **Alto:** MFA/TOTP não imposto na autenticação do Brain. A login atual acessa o Auth do Academy; para exigir AAL2 é necessário implementar enrolamento + challenge + verify também na autorização das operações sensíveis, com recuperação/revogação de fatores.
2. **Alto:** funções `SECURITY DEFINER` na schema public: o advisor marcou 3 funções de trigger executáveis por anon/authenticated. Corrigimos com `REVOKE EXECUTE FROM PUBLIC, anon, authenticated` para `ujn_email_desk_capture_training_after_sent`, `ujn_email_desk_receipt_flag_trigger`, `ujn_email_desk_sent_flag_trigger`. Execução via triggers permanece possível.
3. **Médio/alto:** a API de e-mails possuía autenticação por Bearer e verificação operator, mas sem quota própria nos endpoints de IA e aprovação. Instalamos limitador PostgreSQL atômico: `generate=8/min`, `approve_send=12/min`, `training_toggle=12/min`, `training_exclude=15/min`, por operador. Violação retorna HTTP 429 e evento de auditoria.
4. **Médio:** o login Academy já pode usar proteções nativas do Supabase Auth, mas limites de força bruta, CAPTCHA, notificações e política de senha precisam ser verificados/configurados NO projeto de identidade Academy, não presumidos ativos. O advisor UJN informa que proteção contra senha vazada está desabilitada; não a alteramos automaticamente em produção.
5. **Médio:** GitHub Pages não permite definir livremente cabeçalhos HTTP de resposta do HTML (CSP, HSTS, XFO). No momento, reforçamos esses cabeçalhos na **Edge Function de e-mail**, não no HTML do Pages. Para uma CSP restritiva real do painel é preciso BFF ou CDN/proxy configurável e refatorar CSS/JS inline.
6. **Médio:** HTML de e-mails sanitizado em backend com `sanitize-html@2.17.0`, sem confiar em sanitização de frontend. Continuar revisando outros sinks `innerHTML` e anexos.
7. **Atenção:** parte dos avisos `RLS Enabled No Policy` é proposital: tabelas internas usam service_role, RLS impede acesso direto público. Não criar políticas permissivas apenas para eliminar avisos.
8. **Atenção:** JWT em memória limita persistência após fechar aba, mas pode ser roubado em caso de XSS; `HttpOnly` exige migração deliberada para servidor controlador de sessão.
9. **Atenção:** credenciais de IMAP/SMTP/HMAC permanecem no diretório privado do cPanel e não podem ser compartilhadas no GitHub. A chave pública Supabase `sb_publishable_...` **não é segredo**; a service_role é segredo.

## O que foi implantado AGORA
- Banco privado `ujn_security_audit_events`, RLS ligada, revogação de anon/authenticated, esquema de evento que não registra e-mail, IP, senha nem texto da mensagem;
- Banco privado `ujn_security_request_counters`, limites de janela por operador + ação, operação SQL atômica;
- RPC `ujn_security_limit`, somente service_role, validada em transação de teste com ROLLBACK;
- Edge Function `ujn-email-desk-v1` versão 46: novas proteções HSTS, nosniff, X-Frame-Options, Referrer-Policy, Permissions-Policy e CSP `default-src 'none'` nas respostas JSON; limita rotas sensíveis; registra evento após aprovação de envio de e-mail e quando rate limit for excedido. Não registra conteúdo nem credenciais.
- Github Actions `.github/workflows/brain-security.yml`: CodeQL de Python/JavaScript nos pushes, PRs e semanalmente, e cheque de arquivos de credenciais acidentalmente rastreados;
- Dependabot `.github/dependabot.yml`: revisão semanal de updates de Actions;
- módulo isolado `brain/security/mfa-totp.js`: implementação funcional de funções de enrolamento TOTP, challenge/verify, consulta de fatores e exigência AAL2, usando SDK Supabase Auth. **Não importado no frontend em produção nem MFA obrigatório ainda** para impedir lockout de administradores.
- Sem modificações nos Crons de IMAP, SMTP, Webmail, WhatsApp ou Academy.

## Próximas etapas com ativação controlada
### MFA TOTP — prioridade 1
1. Identificar oficialmente qual Auth é a autoridade para cada operador (Academy/UJN); estabelecer usuário de recuperação e procedimento manual auditado.
2. Integrar `brain/security/mfa-totp.js` no login, permitir enrolar fator TOTP autenticado em AAL1 e confirmar via código de 6 dígitos. Não inserir segredo TOTP em logs, prints, JSON da API editorial ou cache.
3. Usuário já enrolado: desafiar com TOTP após senha e atualizar sessão JWT para AAL2 antes de permitir interface.
4. Gate **server-side** nas Edge Functions e no projeto Academy: rejeitar operações sensíveis de sessão AAL1. O painel sozinho não é mecanismo de segurança.
5. Implantar primeiro em contas de teste, depois operadores, enfim superadmins; só então tornar obrigatório.

### Sessão/cookies — prioridade 2
- Adotar backend-for-frontend próprio em `https://brain.ujn.ojsbr.com` hospedado atrás de HTTPS.
- Usar cookie **`__Host-brain_session`** com `HttpOnly; Secure; SameSite=Strict; Path=/`, sem `Domain`, sessão curta e renovação/rotação explícita.
- Gerar CSRF token aleatório no servidor por sessão, validá-lo via cabeçalho `X-CSRF-Token` para toda mudança de estado; validar Origin e Content-Type. Não misturar tokens Bearer expostos ao browser com cookies persistentes antes do BFF estar pronto.
- HSTS no host do BFF; só habilitar `includeSubDomains` depois de confirmar que TODOS os subdomínios relevantes são HTTPS.

### Hardening do site e API — prioridade 3
- Mover JS/CSS inline para arquivos estáticos com hashes/versionamento; implementar CSP com nonce/hashes válidos e Trusted Types onde suportado.
- Implementar CORS com origin exata; validar JWT no servidor, autorização por recurso (BOLA/IDOR) e escopos por operador em toda Edge Function.
- Rejeitar origem desconhecida e payload > tamanho previsto em todas as APIs, usar schemas Zod/versionados por rota.
- Aplicar rate-limit por **IP confiável do gateway/CDN** também no login, WhatsApp público e envio de formulários. O limitador atual é por operador autenticado e só para a API de e-mails.
- Rate-limit Auth nativo e proteção senha vazada, política de senha, reautenticação antes de ação sensível, revogação de tokens em troca de privilégio.
- Review dos serviços e URLs públicas do Academy, OJS, WhatsApp e SMTP; ajustar cada integração sem compartilhar credenciais.

### Criptografia e segredos — prioridade 4
- Usar hashing administrado pelo Supabase Auth no projeto de autenticação, configurando as opções do fornecedor. Não implementar criptografia caseira de senhas nem gravar hashes manualmente no Brain.
- Segredos do Supabase Edge no Secret Manager do projeto; no cPanel fora de public_html com `chmod 600` e permissões mínimas; GitHub Actions via OIDC quando for preciso deploy e sem publicar service_role.
- Introduzir rotação: MFA recovery, chaves HMAC, SMTP, Meta, OpenAI, Supabase service_role. Chaves passadas em mensagens/conversas devem ser rotacionadas depois de migração segura.
- Auditoria de acesso aos secrets e restore/teste do backup em ambiente isolado.

### CI/CD e segurança contínua — prioridade 5
- CodeQL não substitui teste de intrusão; verificar a execução real no GitHub Actions/Security (não homologada apenas por existir workflow).
- Dependabot para Actions; se dependências npm/pip aparecerem, adicionar workflows/lockfiles e auditoria `npm audit` / `pip-audit`.
- Programar análise de vulnerabilidades, teste DAST autorizado em homologação, revisão de RLS, auditoria de logs, alertas de ataques e incident response.
- Retenção automática de auditoria definida na política interna (p.ex. 90 dias), controle de acesso a eventos e exclusão de dados pessoais indevidos.

## Homologação desta etapa
- Advisor confirmou função `SECURITY DEFINER` executável por anon/authenticated, e a verificação SQL após REVOKE retornou `false` para os três casos.
- Tabelas novas: RLS verificada `true`.
- RPC limitadora: testada com role service em transação e `ROLLBACK`, retornou `allowed=true`. Não foi testado ciclo completo de requisições de produção do browser, nem a execução do workflow em GitHub Actions.
- A Edge Function de e-mails foi publicada v46, sem alteração do comportamento dos cinco Cron.
- MFA, cookie HttpOnly, CSRF para sessões cookie, CSP de todo HTML, limitação por IP e hardening de todas as funções **ainda pendentes**. Não declarar conformidade OWASP total antes da homologação.
