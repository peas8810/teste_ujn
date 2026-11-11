# Coletor de triagem do conteúdo de e-mails — Brain UJN

Arquivo pronto para instalar em `/home/ujn/brain-ujn/brain_ujn_analise_conteudo_imap.py`, ao lado de `imap_config.json`.

## Execução segura (uma vez)
Use o comando abaixo no cPanel (Cron temporário) e remova o Cron após execução:
```bash
/usr/bin/python3 /home/ujn/brain-ujn/brain_ujn_analise_conteudo_imap.py > /home/ujn/brain-ujn/state/ai-content-analysis.log 2>&1
```

Ler `/home/ujn/brain-ujn/state/ai-content-analysis.json`. O script é somente-leitura no IMAP, limitado aos 500 e-mails recentes por pasta. Produz categorias, contagens, quantidade de pareamentos e até 18 pequenos trechos de pergunta/resposta **mascarados de forma básica**; revisar manualmente quaisquer trechos antes de compartilhá-los, pois o mascaramento pode não identificar todos os dados pessoais.

Não faz disparos, não marca mensagens como lidas, não altera o monitor editorial, não exporta anexos ou credenciais. As respostas antigas **não são automaticamente consideradas procedimentos atuais**.

Amostra anterior (assuntos/metadados): 16.497 e-mails recebidos, 5.771 enviados, 1.500 analisados; 546 assuntos coincidentes (não são 546 respostas humanas comprovadas).

## Gestão da IA
O Brain UJN possui `ujn_ai_source_index`, `ujn_ai_knowledge`, `ujn_ai_draft_queue`. Acessar `https://peas8810.github.io/teste_ujn/brain/` > IA · Atendimento. Mensagens do bot e respostas antigas só podem ser promovidas a conhecimento após avaliação de pertinência e atualidade.

**Atenção:** histórico encontrado no Gmail conectado contém propostas de serviços de publicação e promoção com promessas de citações garantidas; esse material é proibido como base de orientações do agente sem revisão institucional e ética.
