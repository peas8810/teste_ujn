# Brain UJN — envio supervisionado com IMAP degradado (19/11/2026)

## Motivo
O coletor IMAP informou `sync_enabled=false` e 1 erro recorrente por minuto. A configuração SMTP permanece `smtp_enabled=true`, `connection_state=VERIFIED` e há registro de SMTP `SENT` nas últimas 24 horas. O bloqueio anterior misturava a saúde do coletor de entrada com a possibilidade de enviar mensagens.

## Medidas implantadas
- RPC `ujn_email_desk_emergency_send_ready(mailbox)`: somente verdadeira com SMTP habilitado e conexão verificada, pasta Enviados configurada, monitor do coletor atualizado há menos de 4 minutos e sucesso SMTP confirmado nas últimas 24 horas.
- Coluna `ujn_email_desk_send_queue.imap_degraded_admin_override`: padrão `false`.
- RPC `ujn_email_desk_claim_send`: mantém o bloqueio normal para mensagens não elegíveis; permite claim de um item com `imap_degraded_admin_override=true` somente se o verificador independente permanecer válido. Não desativa validação de destinatário nem altera a semântica de envio único.
- Ação `approve_send` na edge `ujn-email-desk-v1`: exige usuário com função admin, confirmação `confirm_imap_degraded_send=true`, pré-verificação SMTP e verificação novamente antes de mudar o item aprovado de `PENDING_ACTIVATION` para `QUEUED`. Registra auditoria.
- Portal `brain/index.html`: mostra **Autorizar envio excepcional (IMAP em alerta)** apenas quando a API autoriza; avisa sobre possível ausência de e-mails mais novos e obriga conferir o Webmail e digitar `CONFERI`.
- O status `sync_enabled` continua refletindo a saúde IMAP real. Nenhuma tentativa automática de SMTP é criada apenas pela instalação.

## Como operar
1. Atualizar portal com Ctrl+F5.
2. Conferir no Webmail/Roundcube se existe mensagem nova na conversa ou resposta já enviada.
3. Abrir o rascunho, validar destinatário, assunto e corpo.
4. Clicar em **Autorizar envio excepcional (IMAP em alerta)**, aceitar aviso e digitar exatamente `CONFERI`.
5. Acompanhar status da fila. **QUEUED não é SENT**. Se aparecer `PENDING_ACTIVATION`, `UNKNOWN` ou `FAILED`, NÃO repetir envio até reconciliar.
6. Reparar separadamente a importação IMAP consultando `/home/ujn/brain-ujn/state/imap_maildesk_cron.log` (últimas 30–50 linhas), sem modificar os cinco Cron existentes.

## Garantias e limites
- O SMTP worker continua sendo o único transmissor e nunca tenta novamente job `CLAIMED` ou `UNKNOWN` automaticamente.
- Esse caminho é só do administrador, com confirmação humana adicional.
- O IMAP poderá estar atrasado; conferir Roundcube antes do envio é requisito operacional.
- Últimos testes verificaram o banco, a ativação de elegibilidade, a sintaxe JS e funções; **nenhum envio real foi executado nesta implantação**.
