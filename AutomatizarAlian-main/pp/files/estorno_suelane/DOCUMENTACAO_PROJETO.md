# Documentacao do Projeto - Controle de Estornos

Atualizado em: 2026-05-24

## 1. Visao geral

Este projeto automatiza a geracao de planilhas de controle de estornos a partir de:

- Relatorios PDF de repasse.
- Planilhas XLSX/XLS de comissoes.

O sistema le os PDFs, identifica segurados com comissao negativa, cruza esses segurados com os clientes/vendedores da planilha de comissoes e gera um XLSX de saida formatado.

Atualmente existem dois fluxos:

- **Sistema antigo / Controle de Estornos**: calcula o valor do estorno com regra fixa por quantidade de vendas do vendedor no mes.
- **Estornos Suelane**: calcula o valor do estorno a partir da propria planilha de comissoes, usando `COM CORRETORA` para a vendedora Suelane e `COMISSAO VENDEDOR` para os demais vendedores.

## 2. Como executar

Na pasta que contem `requirements.txt`, instale as dependencias:

```bash
pip install -r requirements.txt
```

Opcoes comuns de execucao:

```bash
streamlit run app.py
```

ou, a partir da pasta `files`:

```bash
streamlit run estorno_suelane/app.py
```

ou, a partir da raiz que contem `files`:

```bash
streamlit run files/estorno_suelane/app.py
```

Dependencias principais:

- `streamlit`: interface web.
- `pdfplumber`: leitura de tabelas/texto do PDF.
- `pandas`: leitura de XLSX/XLS.
- `openpyxl`: escrita do XLSX de saida.
- `thefuzz` e `python-Levenshtein`: match aproximado de nomes.
- `xlrd`: suporte para arquivos `.xls`.

## 3. Estrutura de arquivos

Estrutura principal observada:

```text
files/
  app.py
  matcher.py
  name_normalizer.py
  pdf_parser.py
  README.md
  report_builder.py
  requirements.txt
  test_output.xlsx
  vendor_sales_counter.py
  xlsx_parser.py

  estorno_suelane/
    __init__.py
    app.py
    DOCUMENTACAO_PROJETO.md
    matcher_suelane.py
    new_view.py
    old_view.py
    report_builder_suelane.py
    requirements.txt
    xlsx_parser_suelane.py
```

## 4. Modulos do sistema antigo

### `files/app.py`

Interface Streamlit original do Controle de Estornos.

Responsabilidades:

- Receber upload de PDFs e XLSX/XLS.
- Extrair registros de comissao negativa dos PDFs.
- Extrair cliente, vendedor e apolice das planilhas.
- Cruzar PDF e XLSX.
- Contar vendas por vendedor/mes.
- Gerar `controle_estornos.xlsx`.
- Disponibilizar download.

### `files/pdf_parser.py`

Extrai registros do PDF.

Principais pontos:

- `PDFRecord`: dataclass com `segurado`, `inicio_vig` e `apolice`.
- `extract_negative_commission_records(pdf_path)`: retorna registros com comissao menor que zero.
- `extract_positive_commission_records(pdf_path)`: retorna registros com comissao maior que zero.
- Usa duas estrategias de leitura:
  - `extract_tables()` do `pdfplumber`.
  - Fallback por `extract_text()` com regex.
- Deduplica registros do PDF priorizando linhas que possuem apolice.

### `files/xlsx_parser.py`

Parser do fluxo antigo.

Responsabilidades:

- Encontrar linha de cabecalho com `CLIENTE` e `VENDEDOR`.
- Detectar coluna de apolice.
- Extrair registros `XLSXRecord`.
- Excluir vendedor exatamente igual a `SUELANE` no fluxo antigo.

### `files/name_normalizer.py`

Normaliza e compara nomes.

Regras principais:

- Remove acentos, preservando comportamento especial de `C`/`Ç`.
- Converte para maiusculas.
- Colapsa espacos.
- Compara tokens normalizados.

### `files/matcher.py`

Faz o cruzamento principal entre PDF e XLSX.

Regras principais:

- Primeiro tenta match exato por nome normalizado.
- Depois tenta equivalencia por regra `C`/`Ç`.
- Por fim tenta fuzzy matching.
- Compara apolice pelos ultimos 5 caracteres quando PDF e XLSX possuem apolice.
- Retorna:
  - `matched`: lista de `MatchedRecord`.
  - `not_found`: registros do PDF sem correspondencia.

Tipos de match usados pelo sistema:

- `EXATO`
- `APOLICE_DIFERENTE`
- `FUZZY`
- `FUZZY_APOLICE_DIFERENTE`
- `APOLICE_AUSENTE_XLSX`
- `FUZZY_APOLICE_AUSENTE_XLSX`

### `files/vendor_sales_counter.py`

Calcula a quantidade de vendas por vendedor e mes no fluxo antigo.

Regras:

- Extrai mes/ano a partir do nome da aba.
- Agrupa por `(vendedor, mes)`.
- `get_estorno_value(...)` retorna:
  - `50` se o vendedor tem 4 ou mais vendas no mes.
  - `30` caso contrario.

### `files/report_builder.py`

Gera o XLSX do sistema antigo.

Saida:

- Aba `ESTORNOS`.
- Aba `NAO ENCONTRADOS` quando aplicavel.
- Linhas com match incerto ficam em laranja.
- Valor de estorno vem da regra de R$ 30/R$ 50.

## 5. Modulos do fluxo Estornos Suelane

### `estorno_suelane/app.py`

Entry point Streamlit com menu para selecionar:

- Sistema antigo.
- Nova feature Estornos Suelane.

Este arquivo tambem configura a pagina Streamlit e roteia para `old_view.py` ou `new_view.py`.

### `estorno_suelane/old_view.py`

Replica a tela do sistema antigo dentro do menu novo.

Usa os modulos originais:

- `pdf_parser.py`
- `xlsx_parser.py`
- `matcher.py`
- `vendor_sales_counter.py`
- `report_builder.py`

Tambem preserva a extensao real de uploads `.xls`/`.xlsx` ao criar arquivos temporarios.

### `estorno_suelane/new_view.py`

Tela do fluxo Estornos Suelane.

Versao atual: `1.0.10`.

Responsabilidades:

- Receber PDFs e XLSX/XLS.
- Preservar a extensao original da planilha temporaria (`.xlsx` ou `.xls`) para evitar erro de leitura por engine incorreta.
- Limpar o download anterior quando os arquivos enviados mudam, usando assinatura com hash de conteudo quando possivel.
- Extrair registros negativos dos PDFs.
- Extrair registros do XLSX com colunas de comissao.
- Cruzar registros.
- Mostrar nao encontrados.
- Contar anomalias usando exatamente a mesma regra que pinta as linhas do XLSX.
- Gerar `estornos_suelane.xlsx`.

### `estorno_suelane/xlsx_parser_suelane.py`

Parser XLSX especifico para o fluxo Suelane.

Campos extraidos por registro:

- `cliente`
- `vendedor`
- `sheet_name`
- `apolice`
- `com_corretora`
- `com_vendedor`
- `com_corretora_col_found`
- `com_vendedor_col_found`

Diferencas importantes em relacao ao parser antigo:

- Nao exclui `SUELANE`.
- Detecta `COM CORRETORA` e variantes.
- Detecta `COMISSAO VENDEDOR` e variantes.
- Aceita variantes explicitas de cabecalho para cliente e vendedor, como `SEGURADO`, `NOME DO SEGURADO`, `VEND` e `VENDEDOR RESPONSAVEL`.
- Por compatibilidade, `CONSULTOR` e `CORRETOR` voltaram a ser aceitos como alternativas de cabecalho de vendedor.
- Por compatibilidade, a deteccao de palavras-chave de comissao voltou a usar substring, como antes.
- Registra se a coluna fonte existia na aba.
- Normaliza apolices com protecao para valores como `12345.0`, `1.234,0` e notacao cientifica.
- Converte valores monetarios em formato brasileiro e americano textual quando possivel.
- Evita confundir coluna textual como `VEND/CORRETORA` com coluna de valor `COM CORRETORA`.

### `estorno_suelane/matcher_suelane.py`

Matcher especifico do fluxo Suelane.

Mudanca importante apos esta revisao:

- O fluxo nao faz mais lookup reverso por `sheet_name + vendedor + apolice`.
- O registro XLSX encontrado pela logica de match eh preservado diretamente.
- Isso evita copiar comissao de outro cliente quando ha apolices repetidas, vendedores repetidos ou matches fuzzy.
- Multiplos matches `EXATO` distintos por cliente/vendedor/aba/apolice sao preservados no fluxo Suelane.
- Multiplos matches `FUZZY` com apolice batendo tambem sao preservados no fluxo Suelane.
- Duplicatas identicas por cliente/vendedor/aba/apolice sao colapsadas para reduzir risco de cobranca duplicada.

Campos gerados em `MatchedRecordSuelane`:

- `segurado`
- `inicio_vig`
- `vendedor`
- `match_type`
- `apolice_pdf`
- `apolice_xlsx`
- `sheet_name`
- `com_corretora`
- `com_vendedor`
- `com_corretora_col_found`
- `com_vendedor_col_found`
- `cliente_xlsx`
- `xlsx_duplicate_count`
- `xlsx_duplicate_value_conflict`

Regra de valor:

- Se vendedor normalizado for exatamente `SUELANE`, usa `com_corretora`.
- Caso contrario, usa `com_vendedor`.

Normalizacao de Suelane:

- Aceita caixa diferente: `suelane`, `SUELANE`, `Suelane`.
- Aceita espacos extras e pontuacao final.
- Nao trata `SUELANE J` ou outras variacoes como Suelane exata.

### `estorno_suelane/report_builder_suelane.py`

Gera o XLSX do fluxo Suelane.

Saida:

- Aba `ESTORNOS SUELANE`.
- Aba `NAO ENCONTRADOS` quando aplicavel.

Colunas geradas:

- `CLIENTE`
- `SITUACAO`
- `MES/ABA`
- `VEND/CORRETORA`
- `Nº APOLICE`
- `FONTE DO VALOR`
- `VALOR ESTORNO`
- `OBSERVACAO`

A funcao publica `analyze_record_suelane(record)` concentra a regra de anomalias. A UI usa essa funcao para contar anomalias e o report usa a mesma regra para pintar linhas em laranja.

## 6. Fluxo de processamento Suelane

1. Usuario faz upload de PDF(s) e planilha(s).
2. `pdf_parser.extract_negative_commission_records` encontra segurados com comissao negativa.
3. `xlsx_parser_suelane.extract_client_vendor_pairs_suelane` le todas as abas e extrai cliente/vendedor/apolice/comissoes.
4. `matcher_suelane.match_records_suelane` cruza PDF e XLSX preservando o registro XLSX original retornado pelo match.
5. `report_builder_suelane.analyze_record_suelane` identifica anomalias.
6. `report_builder_suelane.build_report_suelane` gera o arquivo final.
7. Streamlit disponibiliza o download.

## 7. Regras de anomalia no fluxo Suelane

Uma linha eh marcada em laranja quando qualquer uma destas condicoes ocorre:

- Match nao exato.
- Apolice diferente entre PDF e XLSX.
- Match aproximado por nome.
- Apolice ausente na planilha.
- Coluna fonte do valor nao encontrada na aba.
- Valor ausente na coluna fonte.
- Valor zero na coluna fonte.
- Valor negativo na coluna fonte.
- Apolice ausente no PDF.
- Duplicidade no XLSX para o mesmo cliente/vendedor/aba/apolice.
- Duplicidade no XLSX com valores de comissao divergentes.
- Tipo de match desconhecido diferente de `EXATO`.

Mensagens de observacao sao escritas na coluna `OBSERVACAO`.

## 8. Correcoes aplicadas nesta revisao

### 8.1 Lookup ineficaz no matcher Suelane

Problema:

- O fluxo anterior dependia de reconstruir o registro XLSX por uma chave derivada do `MatchedRecord`.
- Fallbacks baseados em poucos campos podiam associar o valor de comissao de outro cliente.
- Em matches fuzzy, o nome do PDF e o nome do XLSX podem ser diferentes, fazendo a busca falhar ou precisar de fallback perigoso.

Solucao:

- `matcher_suelane.py` agora usa a mesma logica base do matcher antigo, mas preserva o `XLSXRecordSuelane` retornado pela busca.
- O enriquecimento do match usa diretamente esse objeto.
- Fallbacks por chave parcial foram removidos.

### 8.2 Boolean e contagem de anomalias

Problema:

- A UI contava anomalias com uma regra manual.
- O XLSX pintava linhas com outra regra interna.
- Qualquer mudanca futura poderia deixar a tela e o relatorio inconsistentes.

Solucao:

- Criada a funcao publica `analyze_record_suelane(record)`.
- `new_view.py` usa essa funcao para contar anomalias.
- `report_builder_suelane.py` usa a mesma regra para pintar linhas.

### 8.3 Colunas de comissao ausentes

Problema:

- Quando `COM CORRETORA` ou `COMISSAO VENDEDOR` nao era encontrada, o registro ficava com valor `None`.
- O relatorio indicava apenas `VALOR AUSENTE`, sem diferenciar celula vazia de coluna inexistente.

Solucao:

- `XLSXRecordSuelane` agora guarda `com_corretora_col_found` e `com_vendedor_col_found`.
- `MatchedRecordSuelane` propaga esses campos.
- O report agora escreve `COLUNA '...' NAO ENCONTRADA NA ABA '...'` quando a coluna fonte nao existe.

### 8.4 Valor zero

Problema:

- Valor `0` passava como se fosse normal.

Solucao:

- `report_builder_suelane.py` marca valor zero como anomalia: `VALOR ZERO NA COLUNA '...'`.
- O valor continua indo para a planilha, mas a linha fica em laranja para revisao.

### 8.5 Parsing de apolices

Problema:

- Valores como `12345.0` podiam virar `123450` apos remocao de pontuacao.
- Valores com notacao cientifica podiam ser normalizados de forma errada.
- Textos com decimal zero em formatos brasileiro/americano tambem eram arriscados.

Solucao:

- Criada conversao intermediaria `_stringify_apolice`.
- Exemplos tratados:
  - `12345.0` -> `12345`
  - `"12345.0"` -> `12345`
  - `"1.2345E+5"` -> `123450`
  - `"1.234,0"` -> `1234`
  - `"1,234.0"` -> `1234`

### 8.6 Deteccao de coluna `COM CORRETORA`

Problema:

- O parser podia aceitar qualquer cabecalho contendo `CORRETORA`.
- Isso podia confundir colunas textuais como `VEND/CORRETORA` com coluna de valor.

Solucao:

- A deteccao agora exige padroes mais especificos como `COM CORRETORA`, `COMISSAO CORRETORA`, `VALOR CORRETORA` ou equivalentes.
- Cabecalhos como `VEND/CORRETORA` nao sao tratados como coluna de valor.

### 8.7 Normalizacao de Suelane

Problema:

- A regra dependia de comparacao textual simples.

Solucao:

- A verificacao de Suelane agora normaliza acentos, pontuacao, caixa e espacos.
- Continua exigindo que o nome normalizado seja exatamente `SUELANE`.

### 8.8 Possiveis valores nulos

Problema:

- Alguns campos eram usados com `.upper()` ou valores diretos assumindo string.

Solucao:

- O matcher Suelane protege os campos principais com fallback para string vazia ao montar `MatchedRecordSuelane`.

### 8.9 Multiplos matches exatos no fluxo Suelane

Problema:

- A logica herdada do matcher antigo escolhia apenas o primeiro match `EXATO`.
- No fluxo Suelane, isso podia esconder outro vendedor ou outra aba valida para o mesmo cliente/apolice.

Solucao:

- `matcher_suelane.py` agora usa uma funcao de busca propria que replica o matcher antigo, mas troca o desempate.
- Matches `EXATO` distintos por cliente/vendedor/aba/apolice sao mantidos.
- Duplicatas identicas por cliente/vendedor/aba/apolice sao colapsadas para evitar dupla cobranca acidental.
- O matcher antigo em `files/matcher.py` nao foi alterado.

### 8.10 Upload `.xls` salvo como `.xlsx`

Problema:

- A UI aceitava `.xls`, mas salvava o arquivo temporario sempre com extensao `.xlsx`.
- Isso podia fazer o `pandas` escolher engine errada ou falhar na leitura de planilhas antigas.

Solucao:

- `new_view.py` e `old_view.py` agora preservam a extensao original `.xls` ou `.xlsx` ao criar o arquivo temporario dentro da pasta `estorno_suelane`.
- O `files/app.py` original foi mantido fora do escopo da nova feature.

### 8.11 Valores monetarios em formato americano

Problema:

- Valores textuais como `1,234,567.89` podiam virar `None`, pois o parser assumia formato brasileiro sempre que havia ponto e virgula.

Solucao:

- `_parse_br_money` agora decide o separador decimal pelo ultimo separador encontrado.
- Exemplos tratados:
  - `1.234.567,89` -> `1234567.89`
  - `1,234,567.89` -> `1234567.89`
  - `-R$ 1.234,56` -> `-1234.56`

### 8.12 Cabecalhos menos rigidos no fluxo Suelane

Problema:

- A aba era ignorada se o cabecalho nao fosse exatamente `CLIENTE` e `VENDEDOR`.

Solucao:

- O parser Suelane aceita variantes explicitas e conservadoras:
  - Cliente/segurado: `CLIENTE`, `SEGURADO`, `NOME CLIENTE`, `NOME DO CLIENTE`, `CLIENTE SEGURADO`, `SEGURADO CLIENTE`, `NOME SEGURADO`, `NOME DO SEGURADO`.
  - Vendedor: `VENDEDOR`, `VEND`, `VENDEDOR RESPONSAVEL`, `RESPONSAVEL VENDA`.
- A deteccao continua evitando termos genericos por substring para nao confundir colunas como `VEND/CORRETORA`.

### 8.13 Apolice ausente no PDF sem alerta

Problema:

- Quando a apolice do PDF estava vazia, o matcher podia classificar o registro como `EXATO` porque o nome batia.
- Isso escondia um risco importante: o match tinha sido feito apenas pelo nome.

Solucao:

- `report_builder_suelane.py` agora marca a linha com `APOLICE AUSENTE NO PDF - MATCH FEITO APENAS PELO NOME`.
- A linha fica em laranja para revisao.

### 8.14 Duplicidade silenciosa no XLSX

Problema:

- Linhas duplicadas no XLSX para o mesmo cliente/vendedor/aba/apolice eram colapsadas para evitar dupla cobranca, mas isso podia esconder valores divergentes.

Solucao:

- `MatchedRecordSuelane` agora carrega:
  - `xlsx_duplicate_count`
  - `xlsx_duplicate_value_conflict`
- O relatorio marca:
  - `DUPLICIDADE NA PLANILHA` quando ha mais de uma linha equivalente.
  - `DUPLICIDADE NA PLANILHA COM VALORES DIVERGENTES` quando os valores de comissao divergem.

### 8.15 Download antigo apos troca de upload

Problema:

- A tela podia manter o botao de download do relatorio anterior mesmo depois de o usuario trocar PDFs ou planilhas e antes de clicar em gerar novamente.
- Isso criava risco operacional de baixar um arquivo antigo achando que era dos novos uploads.

Solucao:

- `new_view.py` e `old_view.py` agora guardam uma assinatura dos arquivos enviados (`nome`, `tamanho`, `tipo` e hash do conteudo quando disponivel).
- O comportamento do `files/app.py` original nao foi alterado por esta protecao.
- Quando a assinatura muda, os bytes de saida sao limpos e o download antigo some.

### 8.16 Multiplos matches fuzzy com apolice batendo

Problema:

- Apos preservar multiplos matches `EXATO`, ainda havia um caso semelhante para `FUZZY`.
- Quando o nome batia por aproximacao e a apolice batia, o fluxo ainda mantinha apenas o primeiro match fuzzy.
- Isso podia omitir outro vendedor/aba valido para o mesmo cliente/apolice.

Solucao:

- `matcher_suelane.py` agora preserva todos os matches `FUZZY` distintos quando a apolice bate.
- As linhas continuam marcadas em laranja por serem `MATCH APROXIMADO PELO NOME`.

### 8.17 Parsing monetario com espaco especial e sinal final

Problema:

- Valores com espaco nao separavel (`1 234,56` vindo como NBSP) podiam virar `None`.
- Valores com sinal negativo no final (`1.234,56-`) tambem nao eram convertidos.
- Celulas booleanas (`TRUE`/`FALSE`) poderiam ser interpretadas como `1.0`/`0.0` se viessem como booleano real.

Solucao:

- `_parse_br_money` remove qualquer espaco unicode.
- `_parse_br_money` reconhece negativo no final.
- Valores booleanos agora retornam `None`, para serem revisados como valor ausente.

### 8.18 Coluna de apolice anterior escolhida por engano

Problema:

- Se uma aba tivesse `APOLICE ANTERIOR` antes de `N APOLICE`, o parser podia escolher a apolice anterior.
- Isso poderia gerar match errado ou marcar apolice divergente sem necessidade.

Solucao:

- `xlsx_parser_suelane.py` agora usa pontuacao/prioridade para cabecalho de apolice.
- Cabecalhos como `N APOLICE`, `N DA APOLICE` e `NUMERO DA APOLICE` tem prioridade.
- Termos como `ANTERIOR`, `ANTIGA`, `CANCELADA` e `VENCIDA` sao ignorados como fonte de apolice atual.

### 8.19 Reversao da prioridade entre `CORRETOR` e `VENDEDOR`

Problema:

- Foi adicionada uma regra de prioridade para escolher `VENDEDOR` antes de `CORRETOR`.
- A alteracao foi considerada arriscada para a compatibilidade do fluxo atual.

Solucao:

- A regra de prioridade foi revertida.
- `xlsx_parser_suelane.py` voltou a usar o comportamento anterior: os cabecalhos aceitos ficam em um conjunto e a primeira coluna aceita encontrada na linha de cabecalho eh usada.
- `CORRETOR` e `CONSULTOR` voltaram a ser aceitos como alternativas de vendedor, como antes dessa alteracao.

### 8.20 Reversao da correspondencia por palavra inteira em comissao

Problema:

- Foi adicionada uma protecao para exigir correspondencia por palavra/frase inteira ao detectar cabecalhos de comissao.
- A alteracao foi considerada arriscada para a compatibilidade com variacoes reais de cabecalho.

Solucao:

- A protecao por palavra inteira foi revertida.
- `_match_keyword` voltou a usar substring simples: se a keyword normalizada aparece dentro do cabecalho normalizado, a coluna pode ser aceita.
- A lista de variantes de comissao do vendedor voltou ao estado anterior dessa alteracao.

### 8.21 Protecao do sistema antigo fora da pasta nova

Problema:

- O escopo original determina que arquivos existentes do sistema antigo nao devem ser alterados.
- Qualquer correcao estrutural deve ficar dentro de `estorno_suelane`, chamando os componentes antigos quando necessario.

Solucao:

- O arquivo `files/app.py` foi restaurado para nao carregar alteracoes da nova feature.
- Correcoes de UI relacionadas ao menu novo permanecem apenas em `estorno_suelane/old_view.py` e `estorno_suelane/new_view.py`.
- Os modulos antigos `matcher.py`, `xlsx_parser.py`, `pdf_parser.py`, `report_builder.py` e `vendor_sales_counter.py` continuam sem alteracoes de logica.

### 8.22 Protecao contra campo nulo na saida Suelane

Problema:

- A geracao do XLSX Suelane usava `.upper()` diretamente em campos de texto antes de escrever a planilha.
- Se algum PDF ou registro intermediario viesse com campo nulo em um caso fora do padrao, o relatorio poderia quebrar depois do cruzamento.

Solucao:

- `report_builder_suelane.py` agora usa conversao segura para texto apenas na exibicao em maiusculas.
- `new_view.py` usa a mesma protecao na deduplicacao de registros PDF do fluxo Suelane.
- A regra principal nao mudou: vendedor `SUELANE` usa `COM CORRETORA`; demais vendedores usam `COMISSAO VENDEDOR`.
- O matcher, os limiares fuzzy e a escolha de valor por linha XLSX nao foram alterados nesta correcao.

### 8.23 Upload reprocessado com cursor ja consumido

Problema:

- No fluxo Suelane, os arquivos enviados eram gravados no temporario usando `uploaded_file.read()`.
- Se o usuario gerasse o relatorio mais de uma vez com os mesmos uploads, o cursor interno do arquivo poderia ja estar no fim e o temporario poderia ser salvo vazio.
- Isso poderia causar erro de leitura de PDF/XLSX antes mesmo do cruzamento.

Solucao:

- `new_view.py` agora usa os bytes estaveis do upload via `getvalue()` quando disponivel.
- O fallback para `.read()` permanece para compatibilidade com objetos que nao tenham `getvalue()`.
- A alteracao fica restrita ao fluxo Suelane e nao muda matching, fuzzy, parser de valores ou a regra `SUELANE -> COM CORRETORA` / demais vendedores -> `COMISSAO VENDEDOR`.

## 9. Validacoes executadas apos as alteracoes

Foram executadas validacoes manuais/sinteticas com Python:

- Compilacao dos arquivos do fluxo Suelane com `python -m compileall .`.
- Normalizacao de apolices:
  - `12345.0`
  - `"12345.0"`
  - `"1.2345E+5"`
  - `"00123-45/67"`
  - `"1.234,0"`
  - `"1,234.0"`
- Parsing de valores monetarios:
  - `"1.234,56"`
  - `"1.234"`
  - `"1234.56"`
  - `"(1.234,56)"`
  - `"1.234.567,89"`
  - `"1,234,567.89"`
  - `"-R$ 1.234,56"`
  - `"1 234,56"` com espaco unicode.
  - `"1.234,56-"`
  - booleanos reais retornando `None`.
- Analise de anomalia para:
  - coluna fonte ausente.
  - valor zero.
  - apolice ausente no PDF.
  - duplicidade no XLSX com valores divergentes.
- Geracao de XLSX Suelane com campos nulos/ausentes em textos exibidos, confirmando que o relatorio nao quebra.
- Escrita de upload do fluxo Suelane com objeto cujo cursor ja foi consumido, confirmando que `getvalue()` preserva os bytes.
- Match fuzzy com outro cliente usando a mesma apolice/vendedor, confirmando que o valor veio do registro XLSX correto.
- Match exato com dois vendedores/abas distintos para o mesmo cliente/apolice, confirmando que duas linhas sao geradas.
- Match fuzzy com dois vendedores/abas distintos e apolice batendo, confirmando que duas linhas sao geradas.
- Duplicata identica por cliente/vendedor/aba/apolice, confirmando que apenas uma linha eh mantida.
- Duplicata com valores divergentes, confirmando que a linha eh marcada em laranja.
- Cabecalho com `APOLICE ANTERIOR` antes de `N APOLICE`, confirmando que a apolice atual eh escolhida.
- Cabecalho com `CORRETOR` antes de `VENDEDOR`, confirmando que o comportamento anterior foi restaurado: a primeira coluna aceita eh usada.
- Cabecalho com apenas `CORRETOR`, confirmando que voltou a ser aceito como alternativa de vendedor.
- Cabecalhos `COM VENDAS`, `VALOR VENDAS` e `TOTAL COM VENDAS`, confirmando que a deteccao por substring voltou ao comportamento anterior.
- Cabecalhos validos `COM VEND` e `COMISSAO VENDEDOR`, confirmando que continuam detectados.
- Deteccao de cabecalho com `NOME DO SEGURADO` e `VENDEDOR RESPONSAVEL`.
- Helpers de extensao temporaria para `.xls`, `.xlsx` e fallback.
- Limpeza de saida anterior quando a assinatura dos uploads muda.
- Geracao temporaria de XLSX com:
  - linha normal.
  - linha com valor zero.
  - aba `NAO ENCONTRADOS`.

## 10. Pontos conhecidos de atencao

- Se o Excel armazenar uma apolice muito longa como numero, o proprio Excel pode ja ter perdido precisao antes do Python ler o arquivo. Para apolices longas, o ideal eh manter a coluna como texto na planilha.
- O matcher compara apolices pelos ultimos 5 caracteres quando PDF e XLSX possuem apolice.
- O matcher fuzzy vem do sistema antigo e usa limiares internos:
  - score maior que 85 quando a apolice bate.
  - score maior que 92 quando a apolice nao bate.
- O parser Suelane espera uma linha de cabecalho com uma das variantes explicitas de cliente/segurado e vendedor. O parser antigo continua esperando `CLIENTE` e `VENDEDOR`.
- Nomes de abas sao usados como informacao de mes/aba, mas o fluxo Suelane nao usa a data do PDF para filtrar a aba.
- Nao ha suite automatizada permanente de testes no projeto; as validacoes desta revisao foram executadas por scripts temporarios.

## 11. Checklist de QA recomendado

Antes de usar em producao, validar com arquivos reais:

- PDF com um unico registro negativo.
- PDF com varios registros negativos.
- PDF onde a apolice aparece na linha seguinte da tabela.
- XLSX com `COM CORRETORA` e `COMISSAO VENDEDOR`.
- XLS e XLSX reais, para confirmar leitura das duas extensoes.
- XLSX sem `COM CORRETORA`.
- XLSX sem `COMISSAO VENDEDOR`.
- XLSX com valor zero.
- XLSX com valor negativo na coluna fonte.
- Cliente com match exato.
- Cliente com dois matches exatos em vendedores/abas diferentes.
- Cliente duplicado de forma identica na planilha.
- Cliente com match fuzzy.
- Cliente com match fuzzy em mais de um vendedor/aba para a mesma apolice.
- Cliente com apolice diferente.
- Cliente sem apolice no PDF.
- Cliente com apolice ausente na planilha.
- Cliente nao encontrado.
- Linhas duplicadas no XLSX com valores iguais.
- Linhas duplicadas no XLSX com valores divergentes.
- Vendedor `SUELANE`, `suelane`, ` Suelane ` e uma variacao como `SUELANE J`.
- Apolices como texto e como numero.
- Planilhas com abas de meses diferentes.
- Cabecalhos alternativos como `NOME DO SEGURADO` e `VENDEDOR RESPONSAVEL`.
- Cabecalhos com `APOLICE ANTERIOR` e `N APOLICE` na mesma aba.
- Cabecalhos com `CORRETOR` e `VENDEDOR` na mesma aba.
- Cabecalhos com apenas `CORRETOR`, confirmando se esse fallback continua desejado operacionalmente.
- Cabecalhos parecidos com comissao, mas que significam vendas, como `COM VENDAS`, pois por compatibilidade a deteccao voltou a usar substring.

## 12. Saidas esperadas

Fluxo antigo:

- Arquivo: `controle_estornos.xlsx`.
- Valor de estorno: R$ 30 ou R$ 50 conforme contagem de vendas.

Fluxo Suelane:

- Arquivo: `estornos_suelane.xlsx`.
- Valor de estorno:
  - Suelane: coluna `COM CORRETORA`.
  - Demais vendedores: coluna `COMISSAO VENDEDOR`.
- Linhas com anomalia ficam em laranja.
- Motivo da anomalia fica na coluna `OBSERVACAO`.
- Downloads antigos sao limpos quando os uploads mudam.

## 13. Manutencao futura

Boas praticas para proximas alteracoes:

- Manter a regra de anomalia centralizada em `analyze_record_suelane`.
- Evitar reintroduzir lookup reverso por chaves parciais no fluxo Suelane.
- Preservar o desempate especifico do Suelane para nao descartar multiplos matches `EXATO` distintos.
- Ao adicionar nova anomalia, garantir que UI e XLSX usem a mesma funcao.
- Ao adicionar novos nomes de coluna, preferir funcoes de deteccao especificas a palavras genericas demais.
- Ao salvar uploads de planilha em arquivo temporario, manter a extensao real do upload.
- Ao alterar a UI, manter a limpeza de output por assinatura dos uploads.
- Ao colapsar duplicatas, preservar o alerta de duplicidade e divergencia de valores no relatorio.
- Ao alterar desempate de matching, validar tanto `EXATO` quanto `FUZZY` com multiplos vendedores/abas.
- Ao mexer em parsing de apolice, testar valores numericos, texto com `.0`, texto com `,0`, notacao cientifica e apolices com zeros a esquerda.
- Ao mexer em deteccao de apolice no XLSX, testar `APOLICE ANTERIOR` antes da apolice atual.
- Ao mexer em deteccao de cabecalhos de vendedor, testar abas com `CORRETOR` e `VENDEDOR` juntos e tambem abas sem `VENDEDOR`.
- Antes de alterar novamente `CORRETOR`/`CONSULTOR`, confirmar a regra de negocio com arquivos reais.
- Ao mexer em deteccao de colunas de comissao, testar abreviacoes validas e efeitos da deteccao por substring.
