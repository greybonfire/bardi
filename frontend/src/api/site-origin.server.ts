import "server-only";

// This is a trust anchor, not a URL to repair. Requiring the serialized origin
// rejects credentials, any path (even /), query, fragment and normalization such
// as whitespace, default ports or encoded hostnames. Never parse browser Origin
// headers this way: those must match the configured value literally.
export function configuredSiteOrigin(): string | null {
  const configured = process.env.BARDI_SITE_ORIGIN
    ?? (process.env.NODE_ENV === "development" ? "http://localhost:3000" : undefined);
  if (!configured) return null;
  try {
    const url = new URL(configured);
    return (url.protocol === "http:" || url.protocol === "https:") && url.origin === configured
      ? configured : null;
  } catch {
    // Configuration and parsing exceptions must never reach logs or responses.
    return null;
  }
}
