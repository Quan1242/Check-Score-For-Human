// Poll the backend callback result; never read credentials or the Google popup URL.
export async function waitForGoogleConnection(
  check: () => Promise<{ connected: boolean }>,
  signal: AbortSignal,
  interval = 1500,
  timeout = 10 * 60 * 1000,
) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    signal.throwIfAborted();
    const status = await check();
    signal.throwIfAborted();
    if (status.connected) return;
    await new Promise<void>((resolve, reject) => {
      const cancel = () => { clearTimeout(timer); reject(signal.reason); };
      const timer = setTimeout(() => { signal.removeEventListener('abort', cancel); resolve(); }, interval);
      signal.addEventListener('abort', cancel, { once: true });
    });
  }
  throw new Error('Phiên cấp quyền đã hết hạn. Bấm lại nút cấp quyền để thử lại.');
}
