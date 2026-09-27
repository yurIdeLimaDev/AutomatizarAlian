import { test, expect } from '@playwright/test';
import path from 'node:path';
test('gera e baixa ambos os relatórios sem enviar documentos', async ({
  page,
  context,
}, testInfo) => {
  const unexpected: string[] = [];
  const errors: string[] = [];
  context.on('request', (request) => {
    // Edge's built-in download panel is browser UI, not an outbound request.
    if (['edge:', 'chrome:', 'devtools:'].includes(new URL(request.url()).protocol)) return;
    if (
      request.method() !== 'GET' ||
      request.postData() ||
      new URL(request.url()).origin !==
        new URL(
          (testInfo.project.use.baseURL as string) ||
            process.env.BASE_URL ||
            'http://127.0.0.1:4173',
        ).origin
    )
      unexpected.push(request.url());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (msg) => {
    if (msg.type() === 'error') console.log('BROWSER:', msg.text());
  });
  for (const flow of ['Gerador de Planilhas', 'Abrir Estorno Suelane']) {
    await page.goto('/');
    await page.getByRole('button', { name: flow, exact: true }).click();
    await page
      .getByLabel('Relatórios de repasse', { exact: true })
      .setInputFiles(path.resolve('../pp/tabelas teste/cenario1_pdf.pdf'));
    await page
      .getByLabel('Planilhas de comissões', { exact: true })
      .setInputFiles(path.resolve('../pp/tabelas teste/cenario1_xlsx.xlsx'));
    await page.getByRole('button', { name: 'Gerar relatório', exact: true }).click();
    await expect(page.getByText('Relatório gerado com sucesso.', { exact: true })).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', { name: /Baixar .*xlsx/ }).click();
    const download = await downloadPromise;
    await download.saveAs(testInfo.outputPath(download.suggestedFilename()));
    await page.screenshot({ path: testInfo.outputPath(flow + '.png'), fullPage: true });
  }
  expect(unexpected).toEqual([]);
  expect(errors).toEqual([]);
});
