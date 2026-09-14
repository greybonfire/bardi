import { createServer } from "node:http";
import { noteKey, notes, planningReply, services } from "./fixtures.mjs";

/**
 * LOCAL TEST SERVER ONLY / خادم اختبار محلي ببيانات اصطناعية فقط.
 * Not a Django replacement, administrative engine, or production dependency.
 * No control endpoints, query toggles, cookies, databases, request logs, traces,
 * analytics, body capture, or mutable cross-test scenario state. Input exists
 * only transiently to choose a known synthetic public response and is discarded.
 *
 * Manual inspection (from frontend, after building):
 *   node --experimental-strip-types e2e/api-stand-in.mjs
 * In another terminal:
 *   BARDI_API_ORIGIN=http://127.0.0.1:8451 BARDI_SITE_ORIGIN=http://localhost:3010 npm run start -- --port 3010
 * Visit /ar or /en, choose a Service, answer the sample questions, and enter
 * TEST-ONLY-NOTE. Both Yes and No work; No shows local research uncertainty.
 * Other allowed TEST-ONLY-* strings are listed in fixtures.mjs. Never enter
 * personal information. The familiar Service titles do not imply real coverage.
 */
const port = process.env.BARDI_E2E_API_PORT ?? "8451";
if (!["8451", "8471"].includes(port)) throw new Error("Unsupported acceptance fixture port.");
const invalid = { type: "invalid", diagnostics: [{ code: "invalid_request", path: [] }] };

function reply(response, status, data, retryAfter) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    ...(retryAfter ? { "Retry-After": retryAfter } : {}),
  });
  response.end(JSON.stringify(data));
}

function syntheticInput(input) {
  if (!input || typeof input !== "object" || Array.isArray(input)) return false;
  if (Object.keys(input).sort().join() !== "evaluation_context,facts,locale,service_id") return false;
  if (!["ar", "en"].includes(input.locale) || typeof input.service_id !== "string") return false;
  const context = input.evaluation_context;
  if (!context || Object.keys(context).join() !== "evaluation_date" || !/^\d{4}-\d{2}-\d{2}$/.test(context.evaluation_date)) return false;
  const facts = input.facts;
  if (!facts || typeof facts !== "object" || Array.isArray(facts)) return false;
  // Narrow allow-list prevents the stand-in from accidentally accepting real
  // names/identifiers or arbitrary payloads during manual browser inspection.
  return Object.entries(facts).every(([key, value]) => {
    if (key === "application_location") return ["inside_egypt", "outside_egypt"].includes(value);
    if (key === "has_required_photos") return typeof value === "boolean";
    if (key === noteKey) return Object.values(notes).includes(value);
    return false;
  });
}

const server = createServer(async (request, response) => {
  try {
    // Happy-path success also proves that Next did not forward browser identity,
    // credentials, or referrers to its upstream API (including SSR navigation).
    if (Object.keys(request.headers).some((key) =>
      ["cookie", "authorization", "referer", "forwarded", "origin", "x-real-ip"].includes(key) || key.startsWith("x-forwarded-"))) {
      reply(response, 400, invalid);
      return;
    }
    if (request.method === "GET" && request.url === "/v1/services") {
      reply(response, 200, { services });
      return;
    }
    if (request.method !== "POST" || request.url !== "/v1/planning") {
      reply(response, 404, invalid);
      return;
    }
    const chunks = [];
    let size = 0;
    for await (const chunk of request) {
      size += chunk.length;
      if (size > 16_384) {
        reply(response, 413, invalid);
        return;
      }
      chunks.push(chunk);
    }
    let input;
    try { input = JSON.parse(Buffer.concat(chunks).toString("utf8")); }
    catch { reply(response, 400, invalid); return; }
    if (!syntheticInput(input)) { reply(response, 422, invalid); return; }
    const result = planningReply(input);
    reply(response, result.status, result.data, result.retryAfter);
  } catch {
    // Do not hand an exception/request/body to Node's default error reporting.
    if (!response.headersSent) reply(response, 503, invalid);
    else response.end();
  }
});
server.requestTimeout = 10_000;
server.on("clientError", (_error, socket) => socket.end("HTTP/1.1 400 Bad Request\r\nConnection: close\r\n\r\n"));
server.on("error", () => {
  process.stderr.write("Synthetic acceptance API could not listen on its configured local port.\n");
  process.exitCode = 1;
});
server.listen(Number(port), "127.0.0.1");
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => {
  server.close();
  server.closeAllConnections();
});
