import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';
// Apply the Pages security policy locally as well, so tests exercise the real CSP.
const headers = Object.fromEntries(
  readFileSync(new URL('./public/_headers', import.meta.url), 'utf8')
    .split('\n')
    .slice(1)
    .filter((line) => line.startsWith('  ') && !line.trim().startsWith('Cache-Control'))
    .map((line) => {
      const i = line.indexOf(':');
      return [line.slice(0, i).trim(), line.slice(i + 1).trim()];
    }),
);
export default defineConfig({
  server: { headers },
  preview: { headers },
  worker: { format: 'es' },
});
