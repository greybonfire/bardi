export function disposableOrigin(env: Record<string, string | undefined>): string {
  const raw = env.BARDI_REAL_E2E_ORIGIN;
  const fail = () => { throw new Error("REAL_E2E_DISPOSABLE_ORIGIN_REQUIRED"); };
  if (env.BARDI_REAL_E2E_DISPOSABLE !== "1" || !raw) return fail();
  let url: URL;
  try { url = new URL(raw); } catch { return fail(); }
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname)
    || url.username || url.password || url.search || url.hash || url.pathname !== "/"
    || raw !== url.origin) return fail();
  return url.origin;
}
