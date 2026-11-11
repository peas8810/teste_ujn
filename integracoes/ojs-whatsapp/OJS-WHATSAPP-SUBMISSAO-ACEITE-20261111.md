# Implantação OJS → Brain UJN: aceite do autor e confirmação de submissão

**Data:** 11/11/2026 · **Escopo:** REMUNOM, RJNM, RSV, JIRRS, NEXUS

## Já implantado no Brain UJN (Supabase)

1. Modelo Meta aprovado `ujn_editorial_update_ptbr`, incluindo evento `submission_received` ("Submissão recebida").
2. Receptor de cópias de notificações OJS → IMAP → Supabase `ujn-editorial-email-ingest`, com HMAC e deduplicação.
3. Reconciliação de confirmações de submissão com autores autorizados: `public.ujn_editorial_reconcile_submission_receipts(30)`, Cron `ujn-editorial-submission-reconcile-5m` a cada 5 minutos. Não encaminha e-mails antigos ou a usuários sem aceitação e verificação.
4. Aprovação `ujn_editorial_wa_approve_verified` e envio `ujn-editorial-wa-dispatch` com Cron de 5 minutos; `ujn-editorial-wa-poll` com Cron de 15 minutos.
5. Registro de aceite para integrações autenticadas: `public.ujn_editorial_register_ojs_acceptance`, preservando o comando PARAR e aceites existentes.
6. Webhook de aceite assinado e servidor-servidor `ujn-editorial-ojs-optin`, status `ACTIVE`. Auditoria privada de versão de termos e evidências em `ujn_editorial_ojs_optin_audit`. O webhook foi implantado, **mas ainda não recebe registros nativos do OJS**.

## Última dependência externa — OJS / provedor da instalação

A leitura autenticada `GET /api/v1/submissions` e `GET /api/v1/submissions/{id}` funcionou nas cinco revistas (HTTP 200). Contudo, a amostra examinada **não expôs telefone, aceite individual ou identificador do consentimento**, nem chave de usuário para consultar perfil. A página de texto `communication-preferences` não é, por si só, aceite auditável.

O administrador/provedor OJS deve conectar o formulário real de submissão ao webhook **depois da confirmação de aceite pelo autor**. A implementação deve:

- Mostrar um controle voluntário e desmarcado para "Quero receber por WhatsApp atualizações editoriais sobre este manuscrito" (com link a termos e política de privacidade atuais). **Não bloquear a submissão** se o autor não aceitar.
- Capturar versão do texto imutável, data e hora, ID da submissão, e-mail confirmado pelo login OJS, telefone E.164 validado, papel (correspondente/autor), evidência de aceite única e o aceite real. Não inferir aceitação de coautores.
- Enviar **uma requisição autenticada do servidor OJS**, antes ou imediatamente após gerar o e-mail de confirmação de submissão. Não utilizar JavaScript público com o segredo.
- Transmitir somente o registro de quem efetivamente optou por WhatsApp editorial. Marketing comercial deve ter aceite separado. Reimportações não podem reativar quem respondeu PARAR sem nova evidência.
- Assegurar que a notificação "submission acknowledgement" do OJS, endereçada ao próprio autor, seja copiada em formato preservando `To`, `Message-ID`, assunto, revista e ID OJS para `contato@ujn.ojsbr.com` (se esse fluxo estiver aprovado pela operação), ou implementar mecanismo equivalente de evento autenticado.
- Fazer teste real com um autor próprio e consentido em cada uma das cinco revistas.

## Contrato do webhook já disponível

URL de serviço:
`https://leytqsyfrmzhectatcqm.supabase.co/functions/v1/ujn-editorial-ojs-optin`

Método: `POST` `application/json`, **somente servidor-servidor**. Cabeçalhos obrigatórios:
- `x-ujn-ojs-timestamp`: Unix timestamp decimal (10 dígitos), com janela de tolerância de 5 minutos
- `x-ujn-ojs-signature`: `sha256=HEX_HMAC_SHA256(secret, timestamp + "." + json_body_exato)`

O segredo distinto `ujn_editorial_ojs_optin_hmac` já está no Supabase Vault. **NÃO** publicá-lo no GitHub, enviá-lo no chat, registrá-lo em logs ou incluí-lo em JavaScript no navegador. O administrador da infraestrutura OJS precisa configurá-lo em ambiente seguro na integração. Não reutilizar os tokens de API de leitura das revistas.

Corpo JSON de exemplo (campos sintéticos, NÃO submeter em produção como autorização real):
```json
{
  "action":"register_editorial_optin",
  "journal":"REMUNOM",
  "submission_id":8390,
  "email":"autor@example.org",
  "phone_e164":"+5533999999999",
  "recipient_role":"corresponding_author",
  "editorial_whatsapp_accepted":true,
  "author_verified_by_ojs":true,
  "marketing_opt_in":false,
  "accepted_at":"2026-11-11T18:10:00Z",
  "policy_version":"1.1",
  "evidence_ref":"ojs:REMUNOM:8390:optin-uuid-exemplo"
}
```

`editorial_whatsapp_accepted=true` e `author_verified_by_ojs=true` devem refletir verificações reais feitas no servidor OJS, e nunca campos inseridos automaticamente. Aceites são válidos se registrados até 30 minutos antes do recebimento pelo webhook, com até 2 minutos de tolerância de relógio no futuro.

Para cada aceitação real recebida, o backend valida assinatura HMAC, campos, formato, janela temporal, evidência única, revogação e vincula telefone ao artigo. Se a mensagem de recebimento chegar até 10 minutos antes da verificação do cadastro OJS, a fila ainda poderá reconciliá-la desde que o aceite real anteceda a mensagem. Não aplica a registros antigos nem a outras origens.

## Estados e testes executados

- Classificação HMAC `submission_received`: 5/5 HTTP 200 em modo `dry_run`, IDs de requisição 1137 a 1141, nenhuma mensagem enviada nos testes.
- Cópias IMAP reais: 7 confirmações recentes da REMUNOM foram classificadas como `submission_received`, mas estão `recipient_unverified` e NÃO foram despachadas.
- Reconciliação automática ativa e testada: retorna `matched=0, queued=0` enquanto não houver destinatário e autorização correspondentes.
- Receptor OJS de aceite assinado está `ACTIVE`; ainda depende da integração nativa ao formulário OJS.
- Nenhum destinatário ou consentimento sintético inserido.

## Operação no painel

`https://peas8810.github.io/teste_ujn/brain/` → **WhatsApp · Marketing** apresenta confirmações recebidas e pendências de vínculo.

Não confundir aceite do modelo Meta com autorização universal dos autores. Não habilitar campanhas de marketing usando aceitações de WhatsApp editorial.

**A implantação na camada OJS exige acesso administrativo ao código/configuração do provedor e não pode ser finalizada apenas com credenciais de leitura da API.**
