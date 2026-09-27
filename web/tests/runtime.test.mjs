import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { createServer } from 'node:http';
import { chromium } from '@playwright/test';

test(
  'Navegador preserva regras, registros e células/estilos da referência Python',
  { timeout: 300000 },
  async (t) => {
    const fixtures = JSON.parse(await readFile('tests/generated/oracle.json', 'utf8'));
    const server = createServer(async (req, res) => {
      const url = new URL(req.url, 'http://localhost');
      const path =
        url.pathname === '/__test_runner.mjs'
          ? resolve('tests/runtime-runner.mjs')
          : resolve('dist', '.' + (url.pathname === '/' ? '/index.html' : url.pathname));
      if (!path.startsWith(resolve('dist')) && path !== resolve('tests/runtime-runner.mjs')) {
        res.writeHead(403).end();
        return;
      }
      try {
        const content = await readFile(path);
        const mime =
          {
            '.js': 'text/javascript',
            '.mjs': 'text/javascript',
            '.wasm': 'application/wasm',
            '.html': 'text/html',
            '.css': 'text/css',
            '.json': 'application/json',
          }[extname(path)] ?? 'application/octet-stream';
        res.writeHead(200, { 'Content-Type': mime }).end(content);
      } catch {
        res.writeHead(404).end();
      }
    });
    await new Promise((done) => server.listen(0, '127.0.0.1', done));
    const browser = await chromium.launch();
    try {
      const page = await browser.newPage();
      await page.goto(`http://127.0.0.1:${server.address().port}`);
      await page.evaluate(() => {
        window.testWorker = new Worker('/__test_runner.mjs', { type: 'module' });
      });
      const call = (data) =>
        page.evaluate(
          (data) =>
            new Promise((resolve, reject) => {
              window.testWorker.onmessage = ({ data }) =>
                data.error ? reject(new Error(data.error)) : resolve(data);
              window.testWorker.onerror = (event) => reject(new Error(event.message));
              window.testWorker.postMessage(data);
            }),
          data,
        );
      const reference = await readFile('tests/oracle.py', 'utf8');
      const helpers = reference.slice(
        reference.indexOf('def workbook_snapshot'),
        reference.indexOf('def make_edge_fixtures'),
      );
      const core = await call({ type: 'init', helpers });
      assert.deepEqual(
        core.result,
        JSON.parse(await readFile('tests/generated/core.json', 'utf8')),
      );
      const results = [];
      for (const fixture of fixtures) {
        await t.test(`${fixture.name}/${fixture.mode}`, async () => {
          async function files(paths, prefix) {
            const out = [];
            for (let i = 0; i < paths.length; i++) {
              const source = paths[i],
                path = `/input/${prefix}${i}.${source.split('.').at(-1)}`;
              out.push({
                path,
                name: source.split('/').at(-1),
                bytes: Array.from(await readFile(resolve('..', source))),
              });
            }
            return out;
          }
          const start = performance.now();
          const { result: actual, workbook } = await call({
            type: 'process',
            mode: fixture.mode,
            pdfs: await files(fixture.pdfs, 'p'),
            sheets: await files(fixture.sheets, 's'),
          });
          for (const key of Object.keys(fixture.expected)) {
            // Assert equality without printing customer contents in CI logs.
            assert.ok(
              JSON.stringify(actual[key]) === JSON.stringify(fixture.expected[key]),
              `${fixture.name}/${fixture.mode}: divergência em ${key}`,
            );
          }
          assert.ok(
            JSON.stringify(workbook) === JSON.stringify(fixture.workbook),
            `${fixture.name}/${fixture.mode}: divergência na planilha`,
          );
          results.push({
            case: `${fixture.name}/${fixture.mode}`,
            pdf: actual.pdfCount,
            spreadsheet: actual.spreadsheetCount,
            matched: actual.matchedCount,
            missing: actual.notFound.length,
            milliseconds: Math.round(performance.now() - start),
          });
        });
      }
      await mkdir('test-results', { recursive: true });
      await writeFile('test-results/parity-summary.json', JSON.stringify(results, null, 2));
    } finally {
      await browser.close();
      await new Promise((done) => server.close(done));
    }
  },
);
