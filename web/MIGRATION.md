# Avaliação do plano e decisões

## Parecer: concordância parcial

O destino Cloudflare Pages e a arquitetura estática fazem sentido: a aplicação trabalha com documentos fornecidos na sessão, não precisa de banco, autenticação ou processamento centralizado. Processamento local atende privacidade e disponibilidade sem manter um servidor.

A reescrita integral em JavaScript/PDF.js/ExcelJS não é o caminho mais seguro para este projeto. O PDF atual usa **duas extrações combinadas**, tabelas do pdfplumber e texto com regex. Mudar o extrator altera reconstrução de linhas e colunas. Há também regras diferentes de desempate no fluxo antigo e no Suelane, interpretação numérica do pandas, normalização de apólices, observações e estilos de relatório que precisariam ser duplicados.

**Decisão:** Vite + TypeScript para interface; Pyodide em Web Worker para executar os módulos Python existentes no navegador. Mantém Pages estático, privacidade e hospedagem gratuita. O custo técnico é um download inicial maior e execução de fuzzy matching Python menos rápida que a extensão nativa. Os exemplos reais foram usados para conferir equivalência e tempo de processamento.

## Mapeamento preservado

| Área | Comportamento original preservado |
|---|---|
| PDF | Tabelas + fallback textual; somente comissões negativas; apólice em sublinha; preferência por apólice preenchida; apólices diferentes permanecem distintas |
| XLS/XLSX | Todas as abas, cabeçalho dinâmico, avisos de abas incompatíveis; engines pandas/openpyxl/xlrd |
| Nomes | NFD, acentos removidos exceto Ç; caixa alta e espaços; comparação Ç/C por token |
| Apólices | Últimos cinco caracteres, ausências distintas de divergências; tratamento numérico especializado no fluxo Suelane |
| Fuzzy | `thefuzz.token_sort_ratio`; score >85 com apólice correspondente, >92 sem correspondência |
| Fluxo antigo | SUELANE exata excluída; primeiro match exato; contagem vendedor/mês da aba; 30 ou 50 por linha |
| Suelane | COM CORRETORA para SUELANE normalizada; COMISSAO VENDEDOR para demais; origem direta do registro |
| Duplicatas Suelane | Chave cliente/vendedor/aba/apólice; primeira origem mantida e contagem/conflito sinalizados |
| XLSX final | Mesmos nomes de abas, cabeçalhos, ordem, valores, fórmula SUM, cores, observações e larguras |
| Estado | Isolado na sessão; download antigo invalidado ao alterar os arquivos; cancelamento libera o worker |

## Diferenças deliberadas

1. Interface responsiva substitui Streamlit; menu e dois fluxos preservados.
2. Nenhum documento é enviado a um servidor. Todos os pacotes públicos são servidos pelo próprio Pages.
3. Orquestração passa para `browser_pipeline.py`; módulos de negócio são copiados sem mudanças e identificados por SHA-256.
4. Renderização raster do pdfplumber não é incluída; nunca é chamada pelos fluxos existentes. Extração usa o código original.
5. Campos de texto que poderiam virar fórmulas em Excel são protegidos, mantendo o TOTAL como fórmula.
6. Cada PDF sem registros identificados ganha um aviso, inclusive quando outros PDFs produzem resultados; isso evita omissões silenciosas em lotes.

## Evidências locais

- 20 combinações comparadas entre Python nativo e WebAssembly em navegador.
- Seis pares sintéticos já presentes no repositório, executados nos dois fluxos.
- Lote real: 3 PDFs e 2 planilhas; 41 registros PDF deduplicados. Fluxo antigo: 1.388 registros de planilhas, 30 matches e 11 não encontrados. Suelane: 1.826 registros, 39 matches e 2 não encontrados. Saídas equivalentes.
- Casos adicionais: XLS e XLSX, múltiplas abas, múltiplos arquivos, nomes/acentos, valores negativos/zero/ausentes, apólices divergentes/ausentes, colunas ausentes, duplicidades com conflito e proteção de fórmulas.
- Comparação semântica de todas as células e estilos dos relatórios, sem exigir bytes ZIP idênticos.

Os documentos do repositório são utilizados apenas nos testes locais/CI. Nenhum deles é copiado para `dist/`.

## Fontes técnicas

- [Pyodide em Web Workers](https://pyodide.org/en/stable/usage/webworker.html)
- [Hospedagem própria do Pyodide](https://pyodide.org/en/stable/usage/downloading-and-deploying.html)
- [Extração de texto e tabelas do pdfplumber](https://github.com/jsvine/pdfplumber)
- [Limites do Cloudflare Pages](https://developers.cloudflare.com/pages/platform/limits/)
