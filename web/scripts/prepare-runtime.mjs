// Build-time downloads only. The deployed app loads all assets from its own origin.
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, copyFile } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { unzipSync, zipSync, strToU8 } from 'fflate';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const runtime = resolve(root, 'public/runtime');
const python = resolve(root, 'public/python');
await mkdir(runtime, { recursive: true });
await mkdir(python, { recursive: true });
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');
async function download(url, expected) {
  const cache = resolve(root, '.cache', sha(url));
  await mkdir(dirname(cache), { recursive: true });
  let bytes;
  try {
    bytes = await readFile(cache);
  } catch {
    /* first build */
  }
  if (!bytes || (expected && sha(bytes) !== expected)) {
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const response = await fetch(url, { signal: AbortSignal.timeout(120000) });
        if (!response.ok) throw new Error(`Download ${response.status}: ${url}`);
        bytes = Buffer.from(await response.arrayBuffer());
        if (expected && sha(bytes) !== expected) throw new Error(`SHA256 divergente: ${url}`);
        await writeFile(cache, bytes);
        break;
      } catch (error) {
        if (attempt === 2) throw error;
      }
    }
  }
  return bytes;
}
const pyodideDir = resolve(root, 'node_modules/pyodide');
const pkg = JSON.parse(await readFile(resolve(pyodideDir, 'package.json')));
const lock = JSON.parse(await readFile(resolve(pyodideDir, 'pyodide-lock.json')));
const cdn = `https://cdn.jsdelivr.net/pyodide/v${pkg.version}/full/`;
for (const name of [
  'pyodide.mjs',
  'pyodide.asm.mjs',
  'pyodide.asm.wasm',
  'python_stdlib.zip',
  'pyodide-lock.json',
]) {
  await copyFile(resolve(pyodideDir, name), resolve(runtime, name));
}
const required = new Set();
function include(name) {
  if (required.has(name)) return;
  const p = lock.packages[name];
  if (!p) throw new Error(`Pacote ausente do Pyodide: ${name}`);
  required.add(name);
  for (const dep of p.depends) include(dep);
}
const packages = ['pandas', 'pillow', 'cryptography'];
packages.forEach(include);
await Promise.all(
  [...required].map(async (name) => {
    const p = lock.packages[name];
    const bytes = await download(cdn + p.file_name, p.sha256);
    await writeFile(resolve(runtime, p.file_name), bytes);
  }),
);

// Versions and hashes are locked once and checked on every build.
const wheelLockPath = resolve(root, 'python-wheels.lock.json');
let wheelLock;
try {
  wheelLock = JSON.parse(await readFile(wheelLockPath));
} catch {
  const versions = {
    pdfplumber: '0.11.10',
    'pdfminer.six': '20260107',
    openpyxl: '3.1.5',
    thefuzz: '0.22.1',
    rapidfuzz: '3.14.6',
    xlrd: '2.0.2',
    'et-xmlfile': '2.0.0',
    'charset-normalizer': '3.5.1',
  };
  wheelLock = [];
  for (const [name, version] of Object.entries(versions)) {
    const meta = JSON.parse(await download(`https://pypi.org/pypi/${name}/${version}/json`));
    // RapidFuzz ships its complete official Python fallback alongside its extension.
    // Extract the Python files, never the native extension, for WebAssembly.
    const wheel =
      meta.urls.find((u) => u.filename.endsWith('none-any.whl')) ??
      (name === 'rapidfuzz' &&
        meta.urls.find((u) => u.filename.endsWith('cp312-cp312-win_amd64.whl')));
    if (!wheel) throw new Error(`Wheel não encontrado: ${name}`);
    wheelLock.push({ name, version, url: wheel.url, sha256: wheel.digests.sha256 });
  }
  await writeFile(wheelLockPath, JSON.stringify(wheelLock, null, 2) + '\n');
}
const entries = {};
for (const wheel of wheelLock) {
  const files = unzipSync(await download(wheel.url, wheel.sha256));
  for (const [name, bytes] of Object.entries(files)) {
    if (name.endsWith('/') || /\.(pyd|dll|so|pyc)$/.test(name)) continue;
    if (name.includes('..') || name.startsWith('/')) throw new Error('Caminho inseguro em wheel');
    entries[name] = bytes;
  }
}
// Only raster rendering is unavailable. Table/text extraction is byte-for-byte upstream.
// This optional pdfplumber dependency is imported by display.py, but never used by our app.
entries['pypdfium2.py'] = strToU8(
  `"""PDF raster rendering is not included in this browser application."""\nclass PdfiumError(Exception):\n    pass\ndef PdfDocument(*args, **kwargs):\n    raise NotImplementedError("Visualizacao raster de PDF indisponivel; extracao de texto e tabelas permanece disponivel.")\n`,
);
const modules = [
  'pdf_parser.py',
  'name_normalizer.py',
  'matcher.py',
  'xlsx_parser.py',
  'vendor_sales_counter.py',
  'report_builder.py',
  'estorno_suelane/__init__.py',
  'estorno_suelane/xlsx_parser_suelane.py',
  'estorno_suelane/matcher_suelane.py',
  'estorno_suelane/report_builder_suelane.py',
];
const sources = {};
for (const name of modules) {
  const bytes = await readFile(resolve(root, '../pp/files', name));
  entries[name] = bytes;
  sources[name] = sha(bytes);
}
entries['browser_pipeline.py'] = await readFile(resolve(root, 'python/browser_pipeline.py'));
const bundle = zipSync(entries, { level: 6 });
await writeFile(resolve(python, 'application.zip'), bundle);
await writeFile(
  resolve(python, 'manifest.json'),
  JSON.stringify(
    {
      pyodide: pkg.version,
      packages,
      sourceHashes: sources,
      applicationSha256: sha(bundle),
      wheels: wheelLock.map(({ name, version }) => ({ name, version })),
    },
    null,
    2,
  ),
);
console.log(
  `Runtime ${pkg.version}; ${required.size} pacotes WASM; ${modules.length} módulos originais preservados.`,
);
