import { readdir, stat, readFile } from 'node:fs/promises';
import { join } from 'node:path';
async function walk(dir) {
  const out = [];
  for (const f of await readdir(dir)) {
    const path = join(dir, f);
    const s = await stat(path);
    if (s.isDirectory()) out.push(...(await walk(path)));
    else out.push({ path, size: s.size });
  }
  return out;
}
const files = await walk('dist');
for (const { path, size } of files) {
  if (size > 25 * 1024 * 1024) throw new Error(`Asset excede limite do Pages: ${path}`);
  if (/(_worker\.js|functions[\\/]|\.(pdf|xlsx?|xlsm))$/i.test(path))
    throw new Error(`Arquivo indevido no site: ${path}`);
}
if (files.length > 20000) throw new Error('Quantidade de assets excede Pages Free');
const html = await readFile('dist/index.html', 'utf8');
if (/https?:\/\//.test(html)) throw new Error('Dependência externa no HTML');
console.log(
  `Build estático verificado: ${files.length} arquivos, ${(files.reduce((n, f) => n + f.size, 0) / 1024 / 1024).toFixed(1)} MiB.`,
);
