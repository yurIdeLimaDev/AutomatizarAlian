# AutomatizarAlian — Controle de Estornos

Geração de controles de estornos a partir de relatórios PDF de repasse e planilhas de comissões XLS/XLSX.

## Versão Web / Cloudflare Pages

Nova interface em `web/`, com os dois fluxos: **Gerador de Planilhas** e **Estorno Suelane**.
O processamento Python acontece dentro do navegador por WebAssembly (Pyodide), sem servidor Python e sem upload de documentos.

Veja [instalação, testes e deploy](web/README.md) e a [avaliação do plano de migração](web/MIGRATION.md).

## Versão Streamlit

A implementação anterior permanece em `pp/files/`, sem alterações.

```bash
pip install -r pp/files/requirements.txt
streamlit run pp/files/estorno_suelane/app.py
```

Documentação anterior: [README do sistema](pp/files/README.md) e [documentação dos dois fluxos](pp/files/estorno_suelane/DOCUMENTACAO_PROJETO.md).
