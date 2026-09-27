# Controle de Estornos — versão web

Aplicação estática para Cloudflare Pages. Interface em TypeScript/Vite; processamento em Python/WebAssembly dentro de um Web Worker do navegador.

## Por que esta arquitetura

Os dez módulos de negócio de `pp/files` são incluídos **sem alterações** no build. Isso preserva a extração por tabelas e texto do pdfplumber, o matching thefuzz, pandas, openpyxl, as duas regras de estorno e a apresentação das planilhas.

O Web Worker é uma thread local do navegador, não um Cloudflare Worker. Não existem Functions, banco, API de upload, telemetria ou backend. Os componentes públicos são servidos pelo próprio site; os documentos permanecem na memória local. Fechar a página, cancelar ou concluir o processamento encerra a instância Python. O resultado fica disponível em memória para download até trocar os arquivos ou sair do fluxo.

## Desenvolvimento

Requisitos: Node.js 24 LTS (mínimo 22.12); Python 3.12 para os testes comparativos. O usuário final não instala nenhum dos dois.

```bash
cd web
npm ci
npm run dev
```

O primeiro preparo baixa dependências com versões fixadas e hashes SHA-256. Os downloads acontecem durante o build; a aplicação publicada não busca dependências em CDNs, PyPI ou GitHub.

```bash
npm run build
npm run preview
```

O build gera somente `dist/`. O script final impede arquivos maiores que 25 MiB, arquivos de entrada PDF/Excel e artefatos de Functions no pacote publicado. **Nunca publique a raiz do repositório**, que contém exemplos de documentos; publique somente `web/dist/`.

## Testes

Na raiz do repositório:

```bash
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r web/tests/requirements.txt
# Linux/macOS:
.venv/bin/python -m pip install -r web/tests/requirements.txt
```

Depois:

```bash
cd web
npx playwright install chromium firefox webkit
npm test
npm run test:e2e -- --project=chromium --project=firefox --project=webkit
# Windows com Edge instalado:
npm run test:e2e -- --project=edge
npm run format:check
npm audit --audit-level=moderate
```

`npm test` encontra `.venv` automaticamente (ou usa `PYTHON`), gera a referência nativa, testa o adaptador, recompila e compara no Chromium o mesmo runtime WASM utilizado pelo site. Compara registros de entrada, matching, não encontrados, avisos, totais, células, fórmulas, fontes, preenchimentos, alinhamentos e larguras. São 20 combinações: seis cenários do repositório, documentos reais, casos de borda XLS/XLSX e múltiplos arquivos, nos dois fluxos.

Os testes de interface cobrem download, privacidade de rede, cancelamento, remoção de arquivos, invalidação de resultados antigos, arquivos corrompidos e layout de 390 px. Arquivos e snapshots gerados ficam ignorados pelo Git e não são publicados. Falhas de equivalência não imprimem dados de clientes no log.

## Cloudflare Pages

Integração Git com `yurIdeLimaDev/AutomatizarAlian`:

| Configuração | Valor |
|---|---|
| Branch de produção | `main` |
| Root directory | `web` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Variável de build | `NODE_VERSION=24` |
| Domínio | domínio gratuito `pages.dev` |

Nenhum binding ou recurso adicional é necessário. Não crie pasta `functions`, `_worker.js`, nem habilite Web Analytics para esta aplicação. `_headers` define a política de segurança; a mesma política é aplicada no preview local usado pelos testes.

O workflow `.github/workflows/web.yml` valida a referência Python, os navegadores e as dependências. Para atualizar, altere o código, execute os testes, abra um PR e aguarde a validação antes de integrar em `main`. O Pages publica automaticamente os commits de produção. A versão Streamlit continua disponível com seu deploy atual.

Em caso de regressão, use o rollback para um deployment anterior no painel Pages e reverta o commit correspondente no GitHub. O rollback do site não altera a versão Streamlit.

## Dependências e manutenção

- `package-lock.json`: Node e runtime Pyodide fixados.
- `python-wheels.lock.json`: versões, URLs oficiais e hashes dos wheels Python.
- `scripts/prepare-runtime.mjs`: inclui somente o código necessário e gera manifesto com hashes dos módulos originais.
- `python/browser_pipeline.py`: adaptação da orquestração Streamlit para memória local; não reimplementa cálculos.
- RapidFuzz usa sua implementação Python oficial. Os scores são comparados com a extensão nativa.
- `pypdfium2` é apenas um adaptador explícito que rejeita renderização raster, funcionalidade não utilizada. A extração de texto/tabelas do pdfplumber e pdfminer permanece original. Não há OCR.
- Os wheels mantêm seus arquivos de licença no pacote distribuído. As licenças do runtime são incluídas no build.

Ao atualizar dependências, renove os locks de forma deliberada e execute novamente toda a comparação. Não edite cópias geradas em `public/python` ou `public/runtime`.

## Limitações

- Aproximadamente 31 MiB de componentes estáticos, com carregamento sob demanda ao gerar o primeiro relatório; o cache do navegador ajuda nos usos seguintes. Não há servidor a acordar.
- PDFs precisam ter texto extraível no formato reconhecido pelo sistema atual. PDFs escaneados, protegidos ou com layout diferente podem exigir adequação do parser.
- Capacidade depende da memória do dispositivo. Não foi imposto um limite de upload menor que o original. Em arquivos muito grandes, prefira computador com memória disponível.
- O fluxo antigo preserva a escolha do primeiro match exato; o fluxo Suelane mantém origens distintas e sinaliza duplicidades/conflitos. Essas regras existentes não foram alteradas.
- A fórmula TOTAL continua recalculável no Excel/LibreOffice. Valores provenientes de arquivos que comecem com `=` são gravados como texto para evitar fórmulas injetadas.
- A hospedagem usa Pages Free e assets estáticos, sujeita aos limites publicados do serviço. Não depende de cartão, domínio próprio ou recursos de backend pagos.
