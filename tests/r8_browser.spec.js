const { test, expect } = require('@playwright/test');
const { execFileSync } = require('node:child_process');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join } = require('node:path');

test('apre il gate R8 con fixture cifrata sintetica e naviga le sezioni', async ({ page }) => {
  const generated = JSON.parse(execFileSync('node', ['tests/generate_r8_fixture.mjs'], { encoding: 'utf8' }));
  try {
    await page.goto('/');
    const component = page.frameLocator('iframe[title="app.cot_r8_full_parity"]');
    await expect(component.locator('#vaultGate')).toBeAttached();
    expect(await component.locator('#vaultGate').evaluate(node => getComputedStyle(node).display)).not.toBe('none');
    await component.locator('#gateOpen').evaluate(button => button.click());
    await component.locator('#encryptedFile').setInputFiles(generated.path);
    await component.locator('#vaultPassword').evaluate((input, password) => {
      input.value = password;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }, generated.password);
    await component.locator('#passwordOk').evaluate(button => button.click());

    await expect(component.locator('#vaultGate')).toBeAttached();
    await expect(component.locator('#vaultGate')).toHaveClass(/hidden/, { timeout: 15_000 });
    await expect(component.locator('#patientsTable tbody tr')).not.toHaveCount(0);
    for (const label of ['Coda COT', 'OdC oggi', 'Lista OdC', 'Percorsi', 'Hospice', 'Strutture', 'Per struttura', 'Per reparto', 'Cruscotto', 'Rettifiche avanzate', 'Qualità dati', 'Dati & backup']) {
      const navButton = component.locator('.nav button').filter({ hasText: label }).first();
      await expect(navButton).toBeAttached();
      const pageName = await navButton.getAttribute('data-page');
      await navButton.evaluate(button => button.click());
      if (pageName) await expect(navButton).toHaveClass(/active/);
    }
  } finally {
    rmSync(generated.path, { force: true });
  }
});
