// Local-only test harness, never copied to dist/. Runs the actual browser WASM.
import { loadPyodide } from '/runtime/pyodide.mjs';
let py;
self.onmessage = async ({ data }) => {
  try {
    if (data.type === 'init') {
      py = await loadPyodide({ indexURL: '/runtime/' });
      const manifest = await (await fetch('/python/manifest.json')).json();
      await py.loadPackage(manifest.packages);
      py.unpackArchive(await (await fetch('/python/application.zip')).arrayBuffer(), 'zip', {
        extractDir: '/app',
      });
      py.runPython(
        "import sys, os, json\nsys.path.insert(0, '/app')\nos.environ['RAPIDFUZZ_IMPLEMENTATION'] = 'python'",
      );
      py.runPython(data.helpers);
      self.postMessage({ result: JSON.parse(py.runPython('json.dumps(core_cases())')) });
    } else {
      py.FS.mkdirTree('/input');
      py.FS.mkdirTree('/output');
      const write = (files) =>
        files.map((file) => {
          py.FS.writeFile(file.path, new Uint8Array(file.bytes));
          return { path: file.path, name: file.name };
        });
      py.globals.set(
        'input_json',
        JSON.stringify({
          mode: data.mode,
          output_dir: '/output',
          pdfs: write(data.pdfs),
          sheets: write(data.sheets),
        }),
      );
      const result = JSON.parse(
        py.runPython('from browser_pipeline import process\nprocess(input_json)'),
      );
      let workbook = null;
      if (result.output) {
        py.globals.set('output_path', result.output);
        workbook = JSON.parse(
          py.runPython('json.dumps(workbook_snapshot(output_path), ensure_ascii=False)'),
        );
      }
      self.postMessage({ result, workbook });
      for (const dir of ['/input', '/output'])
        for (const f of py.FS.readdir(dir))
          if (!['.', '..'].includes(f)) py.FS.unlink(`${dir}/${f}`);
      py.runPython('import gc\ngc.collect()');
    }
  } catch (error) {
    self.postMessage({ error: String(error) });
  }
};
