# Brain UJN — Sessão contínua com segurança (16/11/2026)

## Motivo
O login anterior só guardava `access_token` em variável JavaScript. O navegador perdia o login sempre que a página era recarregada; isso prejudicava especialmente o acesso administrativo.

## Correção aplicada
- `brain/index.html`: armazenamento temporário do **refresh token rotativo** no `sessionStorage` da aba (nunca senha/código TOTP), mantendo access token em memória.
- Ao recarregar a página: token é renovado pelo endpoint Supabase Auth `/auth/v1/token?grant_type=refresh_token` e a sessão só entra no painel depois de validar novamente `bootstrap` e as permissões de operador no servidor Academy.
- Acesso dura **no máximo 12 horas desde o login**, mesmo havendo atualizações/renovações. A renovação ocorre antes de o token de acesso expirar (3 minutos de margem) quando a aba está visível.
- **Sair** limpa o estado local e solicita revogação ao Supabase Auth. Fechar a aba elimina o armazenamento daquela aba. A sessão não é compartilhada com outra máquina.
- Funciona com `F5` e `Ctrl+F5` no mesmo contexto de aba, sem perguntar senha repetidamente.
- Nenhuma modificação em Cron/SMTP/IMAP/WhatsApp e nenhum segredo privado armazenado em GitHub.

## Limitação importante
O `sessionStorage` é acessível ao JavaScript da página: **não é equivalente à proteção HttpOnly** e permanece suscetível a roubo se houver XSS. É uma solução transitória para GitHub Pages estático, com ciclo máximo limitado e reforço de sanitização. A arquitetura desejada é BFF próprio, sessão server-side, cookie `__Host-` com HttpOnly Secure SameSite Strict, CSRF e MFA/AAL2 server-side.

## MFA e superadmin
O administrador superuser também precisa de TOTP quando essa política for ativada, mas o segundo fator deve ser exigido **por sessão/reautenticação sensível**, não em cada refresh da página ou consulta de dados. Código TOTP não deve ser armazenado ou reutilizado.

## Homologação
1. Abrir `https://peas8810.github.io/teste_ujn/brain/` (recarregar com Ctrl+F5) e fazer login uma única vez.
2. Abrir E-mails, navegar normalmente. Pressionar F5; deve mostrar 'Restaurando sua sessão com segurança' e voltar ao painel sem pedir senha.
3. Repetir após alguns minutos, sem quebrar a sincronização com Supabase.
4. Clicar **Sair** e dar F5: deve continuar desconectado.
5. Após fechar a aba e abrir uma nova: deve solicitar login novamente.
6. Avaliar login em conta operador sem autorização: não pode ganhar acesso nem sessão persistida.
7. Verificação atual: GitHub atualizado e inspeção estrutural de código concluída; fluxo real de autenticação do navegador ainda precisa ser testado por operador.

## Próximos ajustes
- Monitorar duração e renovação em uso real.
- Reduzir necessidade de recarregamento ao atualizar telas específicas com eventos/Supabase Realtime, debounce e cache.
- Migrar do Pages para BFF com cookies HttpOnly, reforçar MFA/TOTP e exigir AAL2 no backend para ações sensíveis.
