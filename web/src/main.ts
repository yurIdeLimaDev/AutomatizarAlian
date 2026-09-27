import './styles.css';
import type { Mode, Response, Result } from './types';

const app = document.querySelector<HTMLDivElement>('#app')!;
let mode: Mode | null = null;
let pdfs: File[] = [],
  sheets: File[] = [];
let worker: Worker | null = null;
let downloadUrl: string | null = null;
let generation = 0;

const icons = {
  sheet:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h3m1-4v4"/></svg>',
  arrow:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5"/></svg>',
  upload:
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M12 16V4m-4 4 4-4 4 4M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/></svg>',
};
function el<T extends HTMLElement = HTMLElement>(selector: string): T {
  return app.querySelector<T>(selector)!;
}
function clearResult() {
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl = null;
  const result = app.querySelector('#result');
  if (result) result.replaceChildren();
}
function stop() {
  generation++;
  worker?.terminate();
  worker = null;
}
function shell(content: string) {
  app.innerHTML = `<header class="topbar"><a class="brand" href="#" aria-label="Alian, voltar ao menu"><span class="brand-icon">${icons.sheet}</span><span>alian<span class="brand-sub">CONTROLE DE ESTORNOS</span></span></a><span class="local-badge"><span></span>Processamento local</span></header>
    <main id="main">${content}</main><footer><span>Alian · Controle de Estornos</span><span>PDF + planilhas → relatório pronto</span></footer>`;
  el<HTMLAnchorElement>('.brand').onclick = (event) => {
    event.preventDefault();
    menu();
  };
}
function menu() {
  stop();
  clearResult();
  mode = null;
  pdfs = [];
  sheets = [];
  shell(`<section class="intro"><p class="eyebrow">SUA ROTINA, MAIS SIMPLES</p><h1>Controle de estornos,<br><span>sem trabalho repetitivo.</span></h1><p class="lead">Cruze os relatórios de repasse com as planilhas de comissões e gere seu controle em poucos passos.</p></section>
    <section class="flow-grid" aria-label="Escolha o fluxo">
      <article class="flow-card"><span class="card-icon">${icons.sheet}</span><p class="eyebrow">CONTROLE POR VENDAS</p><h2>Gerador de Planilhas</h2><p>Estornos de R$ 30 ou R$ 50 por linha, conforme as vendas do vendedor no mês. A vendedora Suelane fica fora deste fluxo.</p><button class="primary flow-button" data-mode="old">Gerador de Planilhas ${icons.arrow}</button></article>
      <article class="flow-card"><span class="card-icon secondary-icon">${icons.sheet}</span><p class="eyebrow">CONTROLE POR COMISSÃO</p><h2>Estorno Suelane</h2><p>Inclui todos os vendedores. Usa COM CORRETORA para Suelane e COMISSÃO VENDEDOR para os demais.</p><button class="primary flow-button" data-mode="suelane">Abrir Estorno Suelane ${icons.arrow}</button></article>
    </section><section class="how"><h2>Do arquivo ao relatório</h2><ol><li><span>01</span><div><strong>Selecione os arquivos</strong><p>Um ou mais PDFs e planilhas XLS/XLSX.</p></div></li><li><span>02</span><div><strong>Gere o controle</strong><p>O sistema cruza os dados e sinaliza divergências.</p></div></li><li><span>03</span><div><strong>Confira e baixe</strong><p>Receba a planilha pronta para revisar.</p></div></li></ol></section>
    <aside class="privacy"><strong>Seus arquivos ficam com você.</strong><p>Os documentos são processados na memória do navegador. Ao sair do fluxo ou fechar a página, a seleção é descartada.</p></aside>`);
  app
    .querySelectorAll<HTMLButtonElement>('[data-mode]')
    .forEach((button) => (button.onclick = () => openFlow(button.dataset.mode as Mode)));
}
function openFlow(selected: Mode) {
  stop();
  clearResult();
  mode = selected;
  pdfs = [];
  sheets = [];
  const isSuelane = mode === 'suelane';
  shell(`<button class="back" id="back">← Voltar ao menu</button><section class="flow-intro"><p class="eyebrow">${isSuelane ? 'CONTROLE POR COMISSÃO' : 'CONTROLE POR VENDAS'}</p><h1>${isSuelane ? 'Estorno Suelane' : 'Gerador de Planilhas'}</h1><p class="lead">Selecione os relatórios e as planilhas de comissões para começar.</p></section>
    <aside class="rule"><strong>Como o valor é calculado</strong><p>${isSuelane ? 'SUELANE: COM CORRETORA. Demais vendedores: COMISSÃO VENDEDOR. Valores negativos, zerados ou ausentes, duplicidades e divergências aparecem em laranja, com o motivo na última coluna.' : 'Até 3 vendas no mês: R$ 30 por linha. A partir de 4 vendas: R$ 50. As vendas são contadas nas abas das planilhas. Este fluxo exclui a vendedora SUELANE.'}</p></aside>
    <section class="upload-grid" aria-label="Arquivos de entrada">${uploadArea('pdf', 'Relatórios de repasse', 'PDF', '.pdf')}${uploadArea('sheet', 'Planilhas de comissões', 'XLSX ou XLS', '.xlsx,.xls')}</section>
    <div class="actions"><div><button class="primary" id="run" disabled>Gerar relatório ${icons.arrow}</button><button class="secondary" id="cancel" hidden>Cancelar processamento</button></div><p>Selecione ao menos um arquivo em cada campo.</p></div>
    <div id="status" role="status" aria-live="polite"></div><section id="result" aria-label="Resultado do processamento"></section>
    <aside class="footnote">No primeiro uso, a aplicação carrega os componentes de processamento. Mantenha esta página aberta até a conclusão. Se o formato dos arquivos mudar, procure o responsável pelo sistema.</aside>`);
  el('#back').onclick = menu;
  for (const kind of ['pdf', 'sheet'] as const) {
    el<HTMLInputElement>(`#${kind}-input`).onchange = (event) => {
      addFiles(kind, Array.from((event.target as HTMLInputElement).files ?? []));
      (event.target as HTMLInputElement).value = '';
    };
    const zone = el(`#${kind}-drop`);
    zone.ondragover = (event) => {
      event.preventDefault();
      if (!worker) zone.classList.add('drag');
    };
    zone.ondragleave = () => zone.classList.remove('drag');
    zone.ondrop = (event) => {
      event.preventDefault();
      zone.classList.remove('drag');
      if (!worker) addFiles(kind, Array.from(event.dataTransfer?.files ?? []));
    };
  }
  el('#run').onclick = run;
  el('#cancel').onclick = () => {
    stop();
    setBusy(false);
    status('Processamento cancelado. Você pode ajustar os arquivos e tentar novamente.');
  };
  el('h1').setAttribute('tabindex', '-1');
  el('h1').focus();
}
function uploadArea(kind: string, title: string, format: string, accept: string) {
  return `<article class="upload-card"><h2><span>${kind === 'pdf' ? '01' : '02'}</span>${title}</h2><label class="dropzone" id="${kind}-drop" for="${kind}-input">${icons.upload}<strong>Selecionar ${kind === 'pdf' ? 'PDFs' : 'planilhas'}</strong><span>ou arraste os arquivos até aqui</span><small>${format} · múltiplos arquivos</small><input id="${kind}-input" type="file" accept="${accept}" multiple aria-label="${title}" /></label><ul class="file-list" id="${kind}-list" aria-label="Arquivos selecionados"></ul></article>`;
}
function addFiles(kind: 'pdf' | 'sheet', incoming: File[]) {
  if (worker) return;
  clearResult();
  status('');
  const files = kind === 'pdf' ? pdfs : sheets;
  const invalid: string[] = [];
  for (const file of incoming) {
    if (!(kind === 'pdf' ? /\.pdf$/i : /\.xlsx?$/i).test(file.name) || !file.size) {
      invalid.push(file.name);
      continue;
    }
    if (
      !files.some(
        (f) => f.name === file.name && f.size === file.size && f.lastModified === file.lastModified,
      )
    )
      files.push(file);
  }
  if (invalid.length)
    status(`Arquivos vazios ou em formato não aceito: ${invalid.join(', ')}`, true);
  renderFiles(kind);
  updateRun();
}
function renderFiles(kind: 'pdf' | 'sheet') {
  const list = el(`#${kind}-list`);
  list.replaceChildren();
  const files = kind === 'pdf' ? pdfs : sheets;
  files.forEach((file, index) => {
    const li = document.createElement('li');
    const label = document.createElement('span');
    label.textContent = file.name;
    const size = document.createElement('small');
    size.textContent =
      file.size < 1048576
        ? `${Math.ceil(file.size / 1024)} KB`
        : `${(file.size / 1048576).toFixed(1)} MB`;
    const button = document.createElement('button');
    button.textContent = '×';
    button.setAttribute('aria-label', `Remover ${file.name}`);
    button.onclick = () => {
      if (worker) return;
      files.splice(index, 1);
      clearResult();
      status('');
      renderFiles(kind);
      updateRun();
    };
    li.append(label, size, button);
    list.append(li);
  });
}
function updateRun() {
  el<HTMLButtonElement>('#run').disabled = !!worker || !pdfs.length || !sheets.length;
  el('.actions > p').textContent =
    pdfs.length && sheets.length
      ? `${pdfs.length} PDF(s) e ${sheets.length} planilha(s) selecionados.`
      : 'Selecione ao menos um arquivo em cada campo.';
}
function setBusy(busy: boolean) {
  app
    .querySelectorAll<HTMLInputElement>('.upload-card input, .file-list button')
    .forEach((input) => (input.disabled = busy));
  el('#cancel').hidden = !busy;
  el('#run').innerHTML = busy ? 'Processando…' : `Gerar relatório ${icons.arrow}`;
  el('#main').setAttribute('aria-busy', String(busy));
  updateRun();
}
function status(text: string, error = false) {
  const target = el('#status');
  target.textContent = text;
  target.className = text ? `status ${error ? 'error' : ''}` : '';
  target.setAttribute('role', error ? 'alert' : 'status');
}
async function run() {
  if (!mode || worker || !pdfs.length || !sheets.length) return;
  clearResult();
  const id = ++generation;
  worker = new Worker(new URL('./processor.worker.ts', import.meta.url), { type: 'module' });
  const currentWorker = worker;
  setBusy(true);
  status('Preparando os arquivos…');
  worker.onmessage = ({ data }: MessageEvent<Response>) => {
    if (id !== generation) return;
    if (data.type === 'progress') {
      status(data.message);
      return;
    }
    stop();
    setBusy(false);
    if (data.type === 'error') status(data.message, true);
    else renderResult(data.result, data.bytes);
  };
  worker.onerror = (event) => {
    if (id !== generation) return;
    event.preventDefault();
    stop();
    setBusy(false);
    status(
      'O processamento foi interrompido. Tente novamente em um navegador atualizado, com outras abas pesadas fechadas.',
      true,
    );
  };
  try {
    const read = (files: File[]) =>
      Promise.all(
        files.map(async (file) => ({ name: file.name, bytes: await file.arrayBuffer() })),
      );
    const [p, s] = await Promise.all([read(pdfs), read(sheets)]);
    if (id !== generation) return;
    currentWorker.postMessage(
      { mode, pdfs: p, sheets: s },
      [...p, ...s].map((f) => f.bytes),
    );
  } catch {
    if (id === generation) {
      stop();
      setBusy(false);
      status('Não foi possível abrir os arquivos selecionados. Selecione-os novamente.', true);
    }
  }
}
function renderResult(result: Result, bytes: Uint8Array | null) {
  status(
    result.matchedCount
      ? 'Relatório gerado com sucesso.'
      : result.pdfCount
        ? 'Nenhum registro pôde ser cruzado. Relatório não gerado.'
        : 'Nenhum registro com comissão negativa encontrado nos PDFs.',
    !result.matchedCount,
  );
  const region = el('#result');
  if (bytes) {
    const panel = document.createElement('div');
    panel.className = 'result-panel';
    const h = document.createElement('h2');
    h.textContent = 'Seu controle está pronto';
    const p = document.createElement('p');
    p.textContent = `${result.pdfCount} registros no PDF · ${result.matchedCount} linhas geradas · ${result.anomalies} linhas para conferir`;
    const total = document.createElement('p');
    total.className = 'result-total';
    total.textContent = `Total: ${result.total.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}`;
    const link = document.createElement('a');
    link.className = 'primary';
    link.textContent = `Baixar ${result.filename}`;
    downloadUrl = URL.createObjectURL(
      new Blob([bytes as Uint8Array<ArrayBuffer>], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }),
    );
    link.href = downloadUrl;
    link.download = result.filename;
    panel.append(h, p, total, link);
    if (result.anomalies) {
      const warning = document.createElement('p');
      warning.className = 'review-note';
      warning.textContent =
        'Confira as linhas em laranja e suas observações antes de utilizar os valores.';
      panel.append(warning);
    }
    region.append(panel);
  }
  if (result.warnings.length) details('Avisos sobre os arquivos', result.warnings, region);
  if (result.notFound.length)
    details(
      `${result.notFound.length} segurado(s) não encontrado(s)`,
      result.notFound.map(
        (r) => `${r.segurado} — Início: ${r.inicio_vig} | Apólice: ${r.apolice || 'ausente'}`,
      ),
      region,
    );
}
function details(title: string, messages: string[], parent: HTMLElement) {
  const container = document.createElement('details');
  container.open = true;
  const summary = document.createElement('summary');
  summary.textContent = title;
  const list = document.createElement('ul');
  messages.forEach((message) => {
    const li = document.createElement('li');
    li.textContent = message;
    list.append(li);
  });
  container.append(summary, list);
  parent.append(container);
}
window.addEventListener('pagehide', () => {
  stop();
  clearResult();
});
menu();
