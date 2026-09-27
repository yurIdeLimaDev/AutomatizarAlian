/// <reference lib="webworker" />
import type { Request, Response } from './types';

const scope = self as unknown as DedicatedWorkerGlobalScope;
const send = (response: Response, transfer: Transferable[] = []) =>
  scope.postMessage(response, transfer);
const progress = (message: string) => send({ type: 'progress', message });

// One isolated worker per run. Termination also frees Python/WASM memory and files.
scope.onmessage = async ({ data }: MessageEvent<Request>) => {
  let py: any;
  try {
    progress(
      'Preparando o processamento local. No primeiro uso, o carregamento pode levar um pouco mais de tempo…',
    );
    const origin = new URL('/', scope.location.href);
    const runtimeUrl = new URL('runtime/', origin).href;
    const { loadPyodide } = await import(/* @vite-ignore */ `${runtimeUrl}pyodide.mjs`);
    py = await loadPyodide({ indexURL: runtimeUrl, stdout: () => {}, stderr: () => {} });
    const manifestResponse = await fetch(new URL('python/manifest.json', origin));
    if (!manifestResponse.ok)
      throw new Error('Não foi possível carregar os componentes da aplicação.');
    const manifest = await manifestResponse.json();
    // Install dependencies before their dependants. Concurrent WASM dynamic
    // linking can stall in WebKit even after every wheel has downloaded.
    for (const [index, name] of manifest.packages.entries()) {
      progress(
        `Carregando componentes de processamento (${index + 1}/${manifest.packages.length})…`,
      );
      await py.loadPackage(name, { messageCallback: () => {}, errorCallback: console.error });
    }
    const bundleResponse = await fetch(new URL('python/application.zip', origin));
    if (!bundleResponse.ok) throw new Error('Não foi possível carregar o motor de relatórios.');
    const bundle = await bundleResponse.arrayBuffer();
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bundle)))
      .map((n) => n.toString(16).padStart(2, '0'))
      .join('');
    if (digest !== manifest.applicationSha256)
      throw new Error('Atualização incompleta. Recarregue a página e tente novamente.');
    py.unpackArchive(bundle, 'zip', { extractDir: '/app' });
    py.runPython(
      `import os, sys\nos.environ['RAPIDFUZZ_IMPLEMENTATION'] = 'python'\nsys.path.insert(0, '/app')`,
    );
    py.FS.mkdirTree('/input');
    py.FS.mkdirTree('/output');
    const write = (files: Request['pdfs'], kind: 'pdf' | 'sheet') =>
      files.map((file, i) => {
        const suffix = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
        if (!(kind === 'pdf' ? ['.pdf'] : ['.xls', '.xlsx']).includes(suffix))
          throw new Error(`Formato não aceito: ${file.name}`);
        if (!file.bytes.byteLength) throw new Error(`Arquivo vazio: ${file.name}`);
        const path = `/input/${kind}_${i}${suffix}`;
        py.FS.writeFile(path, new Uint8Array(file.bytes));
        return { name: file.name, path };
      });
    const input = {
      mode: data.mode,
      pdfs: write(data.pdfs, 'pdf'),
      sheets: write(data.sheets, 'sheet'),
      output_dir: '/output',
    };
    // No file bytes, names or report contents are sent through network APIs.
    py.globals.set('input_manifest', JSON.stringify(input));
    py.globals.set('report_progress', progress);
    const result = JSON.parse(
      py.runPython(
        'from browser_pipeline import process\nprocess(input_manifest, report_progress)',
      ),
    );
    const bytes: Uint8Array | null = result.output ? py.FS.readFile(result.output) : null;
    send({ type: 'done', result, bytes }, bytes ? [bytes.buffer as ArrayBuffer] : []);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const pythonMessage = message.match(/ValueError: ([^\n]+)\s*$/)?.[1];
    send({
      type: 'error',
      message:
        pythonMessage ??
        'Não foi possível concluir o processamento. Verifique a conexão para carregar a aplicação e tente novamente. Se persistir, confira os arquivos ou utilize um navegador atualizado.',
    });
    // Developer diagnostics stay local; no telemetry is installed.
    console.error(error);
  } finally {
    if (py) {
      for (const dir of ['/input', '/output']) {
        try {
          for (const name of py.FS.readdir(dir))
            if (name !== '.' && name !== '..') py.FS.unlink(`${dir}/${name}`);
        } catch {
          /* worker is about to terminate */
        }
      }
    }
  }
};
