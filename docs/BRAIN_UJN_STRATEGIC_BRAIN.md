# Strategic Brain — arquitetura, fontes e próximos incrementos

**Data:** 17/11/2026  
**Objetivo:** substituir a antiga aba IA de Atendimento por inteligência editorial/comercial, sem duplicar os assistentes ativos de e-mail e WhatsApp.

## Primeira versão já criada

Frontend: `brain/index.html`, rota de navegação `ai` intitulada **Strategic Brain**.  
Backend: ação de superadministrador `strategic_brain` e `strategic_brain_ai` na Edge Function `ujn-email-desk-v1`.  
Consultas internas agregadas em Postgres:

- `ujn_strategic_brain_snapshot(from,to)`: DDD/UF, contagem de telefones deduplicados, série semanal de cadastros, e-mails e amostra de publicações.
- `ujn_strategic_linkage_snapshot()`: contagens de associações de e-mail/telefone e cadastro editorial verificado, sem emitir identificadores.
- `ujn_strategic_external_snapshot(from,to)`: matrícula INEP, afiliações verificadas e performance de campanhas (quando importados).
- `ujn_strategic_ibge_snapshot()`: população por sexo agregado (quando importado).

Tabelas de recepção com trilha de origem e privilégios restritos ao service_role:
`ujn_strategic_inep_enrollments`, `ujn_strategic_article_affiliations`,
`ujn_strategic_campaign_kpis`, `ujn_strategic_ibge_demographics`.
Nenhuma linha foi inventada ou importada nas quatro tabelas externas no ato da criação.

## Fontes oficiais

- INEP, Censo da Educação Superior (microdados): https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-da-educacao-superior
- INEP, Sinopses por município: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/sinopses-estatisticas/educacao-superior
- INEP, publicação de 09/10/2026: divulgação do Censo 2025 prorrogada até 30/11/2026:
  https://www.gov.br/inep/pt-br/centrais-de-conteudo/noticias/censo-da-educacao-superior/inep-publica-retificacao-sobre-divulgacao-do-censo-da-educacao-superior-2025/
- IBGE, Censo Demográfico 2022, população por sexo e idade:
  https://www.ibge.gov.br/estatisticas/sociais/populacao/22827-censo-demografico-2022.html
- MEC, cadastro de IES/cursos: https://dadosabertos.mec.gov.br/indicadores-sobre-ensino-superior

Sempre guardar o ano, data da atualização, identificação da tabela, URL da fonte, método de agrupamento e informação ausente. **Vagas autorizadas não são alunos matriculados.** População por sexo não é sexo de autores.

## Modelagem de entidades e vínculos

1. Telefone: DDD brasileiro gera somente área de origem provável, não domicílio atual; código 61 agrega DF/GO e não serve para escolher estado sem validação adicional.
2. E-mail ⇄ telefone: vincular por par fornecido pelo autor; marcar como `verificado` apenas quando houver coincidência comprovada de hash do e-mail, telefone, revista e submissão OJS.
3. Artigo ⇄ IES: cruzar DOI/ID do OJS e afiliação explícita validada; não deduzir pela extensão do domínio de e-mail ou pelo nome do autor.
4. Curso ⇄ IES: usar códigos oficiais do INEP/e-MEC e local de oferta; artigo pode ter múltiplas instituições e autores.
5. Sexo/população: somente dados agregados publicados por INEP/IBGE. Não inferir sexo/gênero individual por nome, telefone, e-mail, foto ou profissão.
6. Campanha ⇄ submissão: exigir UTM/campaign_id, evento ArticleRun e submissão OJS verificada, com janela de atribuição declarada.
7. Nenhum dado pessoal bruto segue para a IA estratégica. Requisições da IA trazem apenas totais e estados de proveniência.

## Módulos adicionais recomendados

**A — Mercado endereçável por curso e estado**  
Matrículas, concluintes, docentes/pesquisadores (quando obtidos), IES e oferta presencial/EAD. Exibir ano e qualidade dos dados. Separar graduação, pós-graduação e produção científica.

**B — Funil de captação validado**  
Impressões → cliques → visita ArticleRun → início de submissão → submissão concluída → desk review → decisão → publicação → retorno do autor. Medir conversão, CAC e retorno por periódico/UF/curso, sem condicionar decisões editoriais.

**C — Inteligência de instituições**  
Afiliações verificadas, novos autores, recorrência, diversidade por IES/UF, qualidade temática de artigos, concentração institucional e lacunas territoriais. Uma IES pode existir em vários estados.

**D — Experimentação de mídia paga**  
Campanhas de teste com UTMs e landing pages por área científica/UF, mensuradas por submissões efetivas e margem de contribuição. Controlar orçamento, frequência, conformidade LGPD e separar desempenho de canais e sazonalidade.

**E — Geografia competitiva e previsão**  
Comparar presença observada × matrículas × IES × afiliação × conversão real; criar índice de oportunidade com intervalos de confiança e fonte dos pesos. Não ranquear com amostras mínimas nem confundir correlação com causalidade.

**F — Saúde editorial e qualidade**  
Taxas de desk rejection, tempo de primeira decisão, revisão, transparência APC, reclamações, integridade ética, reclamações de autor e retenção. Não usar IA para prometer aceitação.

## Critérios de homologação

- Dados reais por UF e DDD visíveis somente ao operador administrador; sem retorno de e-mail, telefone ou gênero individual.
- Indicadores sem dados mostram "Aguardando fonte" em vez de zero inventado.
- Série temporal distingue cadastro de contato, e-mail, submissão e publicação.
- Cruzamentos usados em marketing exigem vínculo legítimo, proveniência e objetivo compatível com a LGPD.
- IA retorna observações, hipóteses, plano de validação, indicadores e limitações; não publica campanha, não faz disparos e não altera manuscritos.
- Teste de interface responsiva, de sessão autenticada e de autorização ainda é necessário em ambiente real.

## Etapas pendentes

- Ingerir arquivo oficial INEP 2024 (ou 2025 quando divulgado e auditado) com reconciliação de cursos/IES.
- Ingerir agregados IBGE de sexo e população por UF/município.
- Consultar afiliações verificáveis de artigos nas cinco revistas; remover duplicações por DOI e múltiplas afiliações.
- Integrar eventos do funil de ArticleRun e dos cinco OJS.
- Integrar métricas de Meta Ads e do provedor de e-mail, somente com acesso autorizado.
- Calibrar um índice de priorização estadual após obter dados de conversão suficientes.

## Etapa II — motor de decisões, correlação e mapas (17/11/2026)

Implementado no `brain/index.html` e na versão 61 da Edge Function `ujn-email-desk-v1`:

1. **Árvore de decisão orientada por evidências.** Classifica o que já está disponível e o que ainda falta confirmar em três gates: tamanho do mercado por INEP/IBGE; afiliação acadêmica por DOI/IES; funil de campanhas, submissões e resultado. Só recomenda teste de investimento quando as fontes estão preenchidas e revisadas; os demais caminhos mostram a fonte a importar e o KPI a medir.
2. **Matriz de correlação temporal.** Correlação de Pearson entre seis séries diárias homogêneas de e-mails: recebidas, enviadas, conversas, menções a submissão, pagamentos e pareceres. Usa apenas dias com mensagens sincronizadas, evita interpretar período não importado como zero, sinaliza série curta e não utiliza coeficientes como prova de causalidade.
3. **Matriz de correlação territorial.** Correlações UF×UF entre WhatsApp por DDD, INEP, afiliações institucionais, cliques e submissões pagas, e população IBGE quando existirem oito UFs com pares comparáveis. Não há imputação de zeros para dados faltantes.
4. **Mapa de calor territorial.** Até dez dimensões: contatos/DDD, WhatsApp verificado, matrículas, instituições, cursos, artigos com afiliação verificada, cliques pagos, gastos, submissões atribuídas e população. Intensidade normalizada por coluna, sem falsa comparação de unidades. Estados com contagens pessoais baixas têm valores suprimidos.
5. **Simulador de cenário financeiro.** O administrador informa submissões adicionais, taxa de publicação, receita unitária, custo variável unitário e mídia por mês. Exibe: publicações esperadas, faturamento incremental bruto e contribuição incremental depois dos custos informados; não constitui projeção automática nem permite manipular aceites editoriais.
6. **IA estratégica.** Recebe apenas agregados e indicadores de completude de fonte. Se menos de 21 dias tiverem mensagens sincronizadas, não recebe coeficientes de correlação nem pode recomendá-los como base de gasto. Cada hipótese requer dado, validação, ação, KPI e critério de decisão.

**Importante:** a primeira série disponível de e-mails começa em 05/11/2026. O período de observação ainda não permite projeções sazonais anuais, resultados de mídia paga, nem ROI auditável. As tabelas externas do INEP, IBGE, afiliações e campanhas foram criadas mas ainda precisam ser alimentadas por extrações verificadas. A taxa de aprovação/publicação jamais deve ser forçada por metas comerciais.

### Testes necessários em produção

- Abrir `Strategic Brain` com sessão administrativa e filtro de período.
- Confirmar renderização de árvore, matriz temporal, heatmap e matriz territorial (esta última deve indicar dados externos ausentes).
- Testar simulador com valores controlados; conferir fórmulas manualmente.
- Testar administração negada a operadores sem permissão.
- Verificar relatório IA e confirmar que não cria campanhas nem envia mensagens.

A sintaxe JavaScript foi validada estaticamente no repositório; a experiência de navegador e a geração autenticada da IA exigem homologação com sessão real.
