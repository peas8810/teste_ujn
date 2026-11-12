# Modelo proposto: WhatsApp OJS com link para submissão

**Nome do modelo:** `ujn_editorial_update_link_ptbr`

**Categoria:** Utility

**Idioma:** pt_BR

**Corpo sugerido (aprovação Meta necessária):**

Olá, {{1}}.

Há uma atualização editorial no manuscrito **{{3}}** da revista **{{2}}**.

**Movimentação:** {{4}}.

Para acompanhar sua submissão, utilize o botão abaixo e faça login no OJS.

Editora Unified Journals Network — UJN.

**Botão CTA URL:** `Acompanhar artigo`

**URL base do botão:** `https://peas8810.github.io/teste_ujn/artigo/?ref={{1}}`

**Exemplo de parâmetro dinâmico do botão:** `REMUNOM-8411`

Os quatro parâmetros do corpo preservam a integração existente:
1. Nome de exibição (atualmente `Autor(a)`)
2. Código da revista (ex.: `REMUNOM`)
3. ID do artigo (ex.: `8411`)
4. Nome da movimentação (ex.: `Avaliação iniciada`)

O parâmetro do botão é o sufixo validado `REVISTA-ID`, por exemplo `REMUNOM-8411`. Um redirecionador com lista fechada de cinco revistas abre a URL do OJS no mesmo formato do e-mail de submissão:
`https://remunom.ojsbr.com/multidisciplinar/dashboard/mySubmissions?workflowSubmissionId=8411`.

O login no OJS continua obrigatório; o link não revela conteúdo de avaliações. NÃO substituir o modelo atual `ujn_editorial_update_ptbr` até que o novo seja aprovado na Meta e homologado por envio de teste.
