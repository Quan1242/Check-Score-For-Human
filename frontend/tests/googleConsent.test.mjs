import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/features/googleConsent.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { waitForGoogleConnection } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

test('continues once only after the backend confirms consent', async () => {
  let checks = 0, uploads = 0;
  await waitForGoogleConnection(async () => ({ connected: ++checks === 3 }), new AbortController().signal, 1);
  uploads++;
  assert.equal(checks, 3);
  assert.equal(uploads, 1);
});

test('cancellation during a status request prevents continuation even if consent arrives', async () => {
  const controller = new AbortController();
  await assert.rejects(waitForGoogleConnection(async () => {
    controller.abort();
    return { connected: true };
  }, controller.signal, 1), { name: 'AbortError' });
});

test('missing consent times out without continuing', async () => {
  await assert.rejects(waitForGoogleConnection(async () => ({ connected: false }), new AbortController().signal, 1, 5), /hết hạn/);
});

test('status request failure does not authorize an upload', async () => {
  await assert.rejects(waitForGoogleConnection(async () => { throw new Error('offline'); }, new AbortController().signal, 1), /offline/);
});
