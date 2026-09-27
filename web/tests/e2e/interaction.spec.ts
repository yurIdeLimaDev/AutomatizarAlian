import { test, expect } from '@playwright/test';
import path from 'node:path';

test('troca de arquivos invalida o download e cancelamento permite recomeçar', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Gerador de Planilhas', exact: true }).click();
  const run = page.getByRole('button', { name: 'Gerar relatório', exact: true });
  await expect(run).toBeDisabled();
  await page
    .getByLabel('Relatórios de repasse', { exact: true })
    .setInputFiles(path.resolve('../pp/tabelas teste/cenario1_pdf.pdf'));
  await page
    .getByLabel('Planilhas de comissões', { exact: true })
    .setInputFiles(path.resolve('../pp/tabelas teste/cenario1_xlsx.xlsx'));
  await run.click();
  await page.getByRole('button', { name: 'Cancelar processamento' }).click();
  await expect(page.getByText(/Processamento cancelado/)).toBeVisible();
  await expect(run).toBeEnabled();
  await expect(page.getByRole('link', { name: /Baixar/ })).toHaveCount(0);
  await run.click();
  await expect(page.getByRole('link', { name: /Baixar/ })).toBeVisible();
  await page.getByRole('button', { name: 'Remover cenario1_pdf.pdf' }).click();
  await expect(page.getByRole('link', { name: /Baixar/ })).toHaveCount(0);
  await expect(run).toBeDisabled();
  await page.getByRole('button', { name: 'Voltar ao menu' }).click();
  await page.getByRole('button', { name: 'Abrir Estorno Suelane' }).click();
  await expect(page.getByRole('button', { name: 'Gerar relatório', exact: true })).toBeDisabled();
});

test('arquivo corrompido mostra erro e não oferece relatório parcial', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Gerador de Planilhas', exact: true }).click();
  await page.getByLabel('Relatórios de repasse', { exact: true }).setInputFiles({
    name: 'corrompido.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('not a pdf'),
  });
  await page
    .getByLabel('Planilhas de comissões', { exact: true })
    .setInputFiles(path.resolve('../pp/tabelas teste/cenario1_xlsx.xlsx'));
  await page.getByRole('button', { name: 'Gerar relatório', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('corrompido.pdf');
  await expect(page.getByRole('link', { name: /Baixar/ })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Gerar relatório', exact: true })).toBeEnabled();
});

test('layout móvel mantém navegação e campos dentro da tela', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.screenshot({ path: info.outputPath('menu-mobile.png'), fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Abrir Estorno Suelane' }).click();
  await expect(page.getByLabel('Relatórios de repasse', { exact: true })).toBeAttached();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: info.outputPath('flow-mobile.png'), fullPage: true });
});
