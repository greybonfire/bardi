// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "../app/v1/planning/route";
import { GET } from "../app/v1/services/route";
import { getServices } from "./services.server";
import { API_TIMEOUT_MS, MAX_PLANNING_BODY_BYTES } from "./request.server";
import { input, invalid, jsonResponse, plan, PRIVATE_SENTINEL, results, services } from "./test-fixtures";

const fetchMock = vi.fn<typeof fetch>();
const logMethods = ["debug", "error", "info", "log", "trace", "warn"] as const;
const webOrigin = "https://web.example";
const apiOrigin = "https://django.internal:8443";
const query = `?facts=${PRIVATE_SENTINEL}&url=https://attacker.example/admin&path=/admin`;
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("NODE_ENV", "production");
  vi.stubEnv("BARDI_API_ORIGIN", apiOrigin);
  vi.stubEnv("BARDI_SITE_ORIGIN", webOrigin);
  for (const method of logMethods) vi.spyOn(console, method).mockImplementation(() => undefined);
});
afterEach(() => {
  for (const method of logMethods) expect(console[method]).not.toHaveBeenCalled();
  vi.useRealTimers();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

function post(headers: HeadersInit = {}, signal?: AbortSignal): Request {
  return new Request(`${webOrigin}/v1/planning${query}`, {
    method: "POST", body: JSON.stringify(input), headers, signal,
  });
}
function get(headers: HeadersInit = {}, signal?: AbortSignal): Request {
  return new Request(`${webOrigin}/v1/services${query}`, { headers, signal });
}
function streamingPost(stream: ReadableStream<Uint8Array>, headers: HeadersInit = {}, signal?: AbortSignal): Request {
  const init: RequestInit & { duplex: "half" } = { method: "POST", body: stream, duplex: "half", headers, signal };
  return new Request(`${webOrigin}/v1/planning${query}`, init);
}
function chunksPost(chunks: Uint8Array[], headers: HeadersInit = {}) {
  let position = 0;
  const cancel = vi.fn();
  const request = streamingPost(new ReadableStream({
    pull(controller) {
      if (position < chunks.length) controller.enqueue(chunks[position++]);
      else controller.close();
    },
    cancel,
  }), headers);
  return { request, cancel };
}
async function expectSafeFailure(response: Response, status: number, code: string, path: string[] = []) {
  expect(response.status).toBe(status);
  expect(await response.json()).toEqual({ type: "invalid", diagnostics: [{ code, path }] });
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect([...response.headers.keys()].sort()).toEqual(
    response.headers.has("retry-after") ? ["cache-control", "content-type", "retry-after"] : ["cache-control", "content-type"],
  );
}
const privateHeaders = {
  Origin: webOrigin, Cookie: `case=${PRIVATE_SENTINEL}`, Authorization: `Bearer ${PRIVATE_SENTINEL}`,
  "X-Forwarded-For": "192.0.2.10", "X-Real-IP": "192.0.2.11", Forwarded: "for=192.0.2.12",
  "X-Forwarded-Host": "attacker.example", "X-Forwarded-Proto": "http",
  "CF-Connecting-IP": "192.0.2.13", Referer: `${webOrigin}/${PRIVATE_SENTINEL}`,
  "X-Request-ID": PRIVATE_SENTINEL, "Content-Type": "text/plain", "Retry-After": "123",
};
const hostileResponseHeaders = {
  "Set-Cookie": `session=${PRIVATE_SENTINEL}`, "Cache-Control": "public, max-age=86400",
  "X-Debug": PRIVATE_SENTINEL, "X-Request-ID": PRIVATE_SENTINEL,
  Location: `https://attacker.example/${PRIVATE_SENTINEL}`, Server: PRIVATE_SENTINEL,
  "Access-Control-Allow-Origin": "*", Vary: "Cookie", "Retry-After": "12",
};

function expectPrivateUpstream(endpoint: "services" | "planning") {
  expect(fetchMock).toHaveBeenCalledTimes(1);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe(`${apiOrigin}/v1/${endpoint}`);
  expect(options).toEqual({
    method: endpoint === "services" ? "GET" : "POST",
    headers: endpoint === "services" ? { Accept: "application/json" }
      : { Accept: "application/json", "Content-Type": "application/json" },
    ...(endpoint === "planning" ? { body: expect.any(Uint8Array) } : {}),
    credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer", redirect: "manual",
    signal: expect.any(AbortSignal),
  });
  if (endpoint === "planning") {
    expect(new TextDecoder().decode(options?.body as Uint8Array)).toBe(JSON.stringify(input));
  }
}

describe("same-origin route handlers", () => {
  it.each(results)("whitelists $type, drops queries and all inbound/outbound private headers", async (result) => {
    fetchMock.mockResolvedValue(jsonResponse(result, 200, hostileResponseHeaders));
    const response = await POST(post(privateHeaders));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(result);
    expect([...response.headers]).toEqual([
      ["cache-control", "no-store"], ["content-type", "application/json; charset=utf-8"],
    ]);
    expectPrivateUpstream("planning");
  });

  it("exposes only Service navigation with no cache or header propagation", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ services }, 200, hostileResponseHeaders));
    const response = await GET(get(privateHeaders));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ services });
    expect([...response.headers]).toEqual([
      ["cache-control", "no-store"], ["content-type", "application/json; charset=utf-8"],
    ]);
    expectPrivateUpstream("services");
  });

  it.each([400, 413, 422])("preserves validated HTTP %i invalid diagnostics", async (status) => {
    fetchMock.mockResolvedValue(jsonResponse(invalid, status, hostileResponseHeaders));
    const response = await POST(post());
    expect(response.status).toBe(status);
    expect(await response.json()).toEqual(invalid);
    expect([...response.headers.keys()].sort()).toEqual(["cache-control", "content-type"]);
  });

  it.each([400, 413, 422])("rejects non-invalid payloads at HTTP %i", async (status) => {
    fetchMock.mockResolvedValue(jsonResponse(plan, status));
    await expectSafeFailure(await POST(post()), 502, "unexpected_response");
  });

  it.each([500, 501, 502, 503, 504, 599])("normalizes upstream HTTP %i without passing debug/error bodies", async (status) => {
    fetchMock.mockImplementation(async () => new Response(`<html>${PRIVATE_SENTINEL}</html>`, {
      status, headers: { ...hostileResponseHeaders, "Retry-After": "30" },
    }));
    for (const response of [await POST(post()), await GET(get())]) {
      await expectSafeFailure(response, 503, "unavailable");
      expect(response.headers.get("retry-after")).toBe("30");
    }
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each(["0", "42", "86400", "99999", "9999999999999999", "-1", "1.5", PRIVATE_SENTINEL, "Wed, 21 Oct 2030 07:28:00 GMT"])(
    "retains 429 rate policy but only bounded decimal Retry-After: %s", async (value) => {
      fetchMock.mockImplementation(async () => new Response(PRIVATE_SENTINEL, {
        status: 429, headers: { ...hostileResponseHeaders, "Retry-After": value },
      }));
      for (const response of [await POST(post()), await GET(get())]) {
        await expectSafeFailure(response, 429, "rate_limited");
        expect(response.headers.get("retry-after")).toBe(["0", "42", "86400"].includes(value) ? value : null);
      }
      expect(fetchMock).toHaveBeenCalledTimes(2);
    },
  );

  it.each([201, 202, 204, 205, 206, 301, 302, 303, 304, 307, 308, 401, 403, 404, 405, 415, 418])(
    "never forwards non-contract HTTP %i or redirects", async (status) => {
      fetchMock.mockImplementation(async () => new Response(null, { status, headers: hostileResponseHeaders }));
      await expectSafeFailure(await POST(post()), 502, "unexpected_response");
      await expectSafeFailure(await GET(get()), 502, "unexpected_response");
    },
  );

  it.each([
    () => new Response(`{"data":${PRIVATE_SENTINEL}`, { headers: { "Content-Type": "application/json" } }),
    () => new Response(`<html>${PRIVATE_SENTINEL}</html>`, { headers: { "Content-Type": "text/html" } }),
    () => new Response(JSON.stringify(invalid)),
    () => jsonResponse(null), () => jsonResponse([]), () => jsonResponse({ type: "other" }),
    () => jsonResponse({ ...invalid, facts: input.facts }),
    () => jsonResponse({ ...plan, routing: { ...plan.routing, rule: PRIVATE_SENTINEL } }),
    () => jsonResponse({ ...plan, fees: [{ ...plan.fees[0], evidence_links: [PRIVATE_SENTINEL] }] }),
  ])("sanitizes malformed JSON, media types and nested response fields %#", async (response) => {
    fetchMock.mockResolvedValue(response());
    await expectSafeFailure(await POST(post()), 502, "unexpected_response");
  });

  it.each([
    "", "null", "https://attacker.example", "http://web.example", "https://web.example:444",
    "https://web.example.attacker.example", `${webOrigin}, https://attacker.example`, `${webOrigin} ${webOrigin}`,
    `${webOrigin}/`, `${webOrigin}/path/..`, `${webOrigin}?`, `${webOrigin}?query=1`, `${webOrigin}#`, `${webOrigin}#fragment`,
    "https://user:password@web.example", "https://@web.example", "https://:@web.example",
    "HTTPS://web.example", "https://WEB.example", "https://web.example:443", "https://web.example.",
    "https://%77eb.example", "https:\\\\web.example", `blob:${webOrigin}/opaque`, "data:text/plain,opaque",
  ])(
    "blocks foreign, opaque and non-literal Origin %s before reading or forwarding a body", async (origin) => {
      const cancel = vi.fn();
      const request = streamingPost(new ReadableStream({ cancel }), { Origin: origin });
      await expectSafeFailure(await POST(request), 403, "forbidden_origin");
      expect(fetchMock).not.toHaveBeenCalled();
      expect(cancel).toHaveBeenCalledTimes(1);
    },
  );

  it("does not trust spoofed Host or forwarded hosts when validating Origin", async () => {
    await expectSafeFailure(await POST(post({
      Origin: "https://attacker.example", Host: "attacker.example", "X-Forwarded-Host": "attacker.example",
      "X-Forwarded-Proto": "https", Forwarded: "host=attacker.example;proto=https", "Sec-Fetch-Site": "same-origin",
    })), 403, "forbidden_origin");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([undefined, webOrigin])("blocks browser cross-site POSTs even with missing or matching Origin %#", async (origin) => {
    await expectSafeFailure(await POST(post({
      ...(origin === undefined ? {} : { Origin: origin }), "Sec-Fetch-Site": "cross-site",
    })), 403, "forbidden_origin");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sanitizes transport exceptions and never retries POST", async () => {
    fetchMock.mockRejectedValue(new Error(`credentials@internal/${PRIVATE_SENTINEL}`));
    await expectSafeFailure(await POST(post()), 503, "unavailable");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("lets Django produce malformed-body diagnostics without parsing, echoing, or changing input bytes", async () => {
    const bytes = new TextEncoder().encode(`{bad json ${PRIVATE_SENTINEL}`);
    fetchMock.mockResolvedValue(jsonResponse(invalid, 400));
    const response = await POST(chunksPost([bytes]).request);
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual(invalid);
    expect(fetchMock.mock.calls[0][1]?.body).toEqual(bytes);
  });
});

describe("configured public planning origin", () => {
  const listenerOrigin = "http://127.0.0.1:3010";

  it.each([
    "http://localhost:3010", "https://web.example", "https://public.example:8443", "http://[::1]:3010",
  ])("accepts literal public Origin %s independently of the listener URL and untrusted host headers", async (origin) => {
    vi.stubEnv("BARDI_SITE_ORIGIN", origin);
    fetchMock.mockResolvedValue(jsonResponse(plan));
    const response = await POST(new Request(`${listenerOrigin}/v1/planning${query}`, {
      method: "POST", body: JSON.stringify(input), headers: {
        ...privateHeaders, Origin: origin, Host: "attacker.example", "Sec-Fetch-Site": "same-origin",
      },
    }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(plan);
    expectPrivateUpstream("planning");
  });

  it("rejects a listener-matching Origin when it differs from the configured public origin", async () => {
    fetchMock.mockResolvedValue(jsonResponse(plan));
    const cancel = vi.fn();
    const pull = vi.fn((controller: ReadableStreamDefaultController<Uint8Array>) => {
      controller.enqueue(new TextEncoder().encode(JSON.stringify(input)));
      controller.close();
    });
    const init: RequestInit & { duplex: "half" } = {
      method: "POST", duplex: "half", body: new ReadableStream({ pull, cancel }, { highWaterMark: 0 }), headers: {
        Origin: listenerOrigin, Host: "127.0.0.1:3010", "X-Forwarded-Host": "web.example",
        "X-Forwarded-Proto": "https", "Sec-Fetch-Site": "same-origin",
      },
    };
    await expectSafeFailure(await POST(new Request(`${listenerOrigin}/v1/planning`, init)), 403, "forbidden_origin");
    expect(pull).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it("allows missing Origin for public stateless clients without forwarding credentials or host identity", async () => {
    fetchMock.mockResolvedValue(jsonResponse(plan));
    const headers = new Headers({ ...privateHeaders, Host: "attacker.example" });
    headers.delete("origin");
    const response = await POST(new Request(`${listenerOrigin}/v1/planning${query}`, {
      method: "POST", body: JSON.stringify(input), headers,
    }));
    expect(response.status).toBe(200);
    expectPrivateUpstream("planning");
  });

  it.each([
    undefined, "", "null", `not-a-url-${PRIVATE_SENTINEL}`, "//web.example", `file:///${PRIVATE_SENTINEL}`,
    "ftp://web.example", `blob:${webOrigin}/opaque`, `https://user:${PRIVATE_SENTINEL}@web.example`,
    "https://@web.example", "https://:@web.example", `${webOrigin}/`, `${webOrigin}/${PRIVATE_SENTINEL}`,
    `${webOrigin}/path/..`, `${webOrigin}?`, `${webOrigin}?secret=${PRIVATE_SENTINEL}`, `${webOrigin}#`,
    `${webOrigin}#${PRIVATE_SENTINEL}`, ` ${webOrigin}`, `${webOrigin} `, `${webOrigin}\n`, "https://we\tb.example",
    "HTTPS://web.example", "https://WEB.example", "https://web.example:443", "http://localhost:03010",
    "https://%77eb.example", "https:\\\\web.example", `${webOrigin},https://attacker.example`,
  ])("fails closed before reading for missing, invalid or non-canonical production site configuration %#", async (origin) => {
    vi.stubEnv("BARDI_SITE_ORIGIN", origin);
    const cancel = vi.fn();
    const pull = vi.fn((controller: ReadableStreamDefaultController<Uint8Array>) => {
      controller.enqueue(new TextEncoder().encode(JSON.stringify(input)));
      controller.close();
    });
    const request = streamingPost(new ReadableStream({ pull, cancel }, { highWaterMark: 0 }), privateHeaders);
    await expectSafeFailure(await POST(request), 503, "unavailable");
    expect(pull).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it.each([undefined, "", `${webOrigin}/${PRIVATE_SENTINEL}`])("keeps public GET and direct navigation independent of site configuration %#", async (origin) => {
    vi.stubEnv("BARDI_SITE_ORIGIN", origin);
    fetchMock.mockImplementation(async () => jsonResponse({ services }));
    const response = await GET(get({ ...privateHeaders, Origin: "null", "Sec-Fetch-Site": "cross-site" }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ services });
    expectPrivateUpstream("services");
    fetchMock.mockClear();
    expect(await getServices()).toEqual({ ok: true, services });
    expectPrivateUpstream("services");
  });

  it("uses exactly the documented public localhost origin only when unset in development", async () => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("BARDI_SITE_ORIGIN", undefined);
    fetchMock.mockResolvedValue(jsonResponse(plan));
    const request = new Request("http://127.0.0.1:3000/v1/planning", {
      method: "POST", body: JSON.stringify(input), headers: { Origin: "http://localhost:3000" },
    });
    expect((await POST(request)).status).toBe(200);
    expectPrivateUpstream("planning");
    fetchMock.mockClear();
    for (const origin of ["http://127.0.0.1:3000", "http://localhost:3010"]) {
      await expectSafeFailure(await POST(post({ Origin: origin })), 403, "forbidden_origin");
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([undefined, "production", "test"])("never derives a missing site origin from requests, public env or defaults outside development %#", async (mode) => {
    vi.stubEnv("NODE_ENV", mode);
    vi.stubEnv("BARDI_SITE_ORIGIN", undefined);
    vi.stubEnv("NEXT_PUBLIC_BARDI_SITE_ORIGIN", webOrigin);
    const callerHeaders: HeadersInit[] = [{}, { Origin: webOrigin, Host: "web.example", "X-Forwarded-Host": "web.example" }];
    for (const headers of callerHeaders) {
      await expectSafeFailure(await POST(post(headers)), 503, "unavailable");
    }
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each(["", `${webOrigin}/path`])("does not silently default invalid development configuration %#", async (origin) => {
    vi.stubEnv("NODE_ENV", "development");
    vi.stubEnv("BARDI_SITE_ORIGIN", origin);
    await expectSafeFailure(await POST(post({ Origin: "http://localhost:3000" })), 503, "unavailable");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([undefined, "https://attacker.example"])("releases the deadline on origin/configuration rejection without awaiting stalled cancellation %#", async (origin) => {
    vi.useFakeTimers();
    if (origin === undefined) vi.stubEnv("BARDI_SITE_ORIGIN", undefined);
    const cancel = vi.fn(() => new Promise<void>(() => undefined));
    const response = await POST(streamingPost(new ReadableStream({ cancel }), origin ? { Origin: origin } : {}));
    await expectSafeFailure(response, origin === undefined ? 503 : 403, origin === undefined ? "unavailable" : "forbidden_origin");
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("bounded request streams", () => {
  it.each([undefined, "0", "1", String(MAX_PLANNING_BODY_BYTES)])("accepts exactly 512 KiB with Content-Length %s", async (length) => {
    const bytes = new TextEncoder().encode(JSON.stringify(input).padEnd(MAX_PLANNING_BODY_BYTES, " "));
    fetchMock.mockResolvedValue(jsonResponse(invalid, 422));
    const { request } = chunksPost([bytes.subarray(0, 137), bytes.subarray(137)], length === undefined ? {} : { "Content-Length": length });
    const response = await POST(request);
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual(invalid);
    expect(fetchMock.mock.calls[0][1]?.body).toEqual(bytes);
  });

  it.each([undefined, "0", "1", "invalid", String(MAX_PLANNING_BODY_BYTES)])("rejects actual overflow despite Content-Length %s", async (length) => {
    const { request, cancel } = chunksPost([
      new Uint8Array(MAX_PLANNING_BODY_BYTES), new Uint8Array(1), new Uint8Array(10),
    ], length === undefined ? {} : { "Content-Length": length });
    await expectSafeFailure(await POST(request), 413, "body_too_large", ["body"]);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(cancel).toHaveBeenCalledTimes(1);
  });

  it("counts UTF-8 bytes, not decoded characters", async () => {
    const bytes = new TextEncoder().encode("😀".repeat(MAX_PLANNING_BODY_BYTES / 4 + 1));
    await expectSafeFailure(await POST(chunksPost([bytes]).request), 413, "body_too_large", ["body"]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([String(MAX_PLANNING_BODY_BYTES + 1), "9".repeat(100)])("rejects declared overflow early: %s", async (length) => {
    const cancel = vi.fn();
    const request = streamingPost(new ReadableStream({ cancel }), { "Content-Length": length });
    await expectSafeFailure(await POST(request), 413, "body_too_large", ["body"]);
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sanitizes stream errors", async () => {
    const request = streamingPost(new ReadableStream({
      start(controller) { controller.error(new Error(PRIVATE_SENTINEL)); },
    }));
    await expectSafeFailure(await POST(request), 400, "invalid_body", ["body"]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("allows empty bodies through to backend validation", async () => {
    fetchMock.mockResolvedValue(jsonResponse(invalid, 400));
    const response = await POST(new Request(`${webOrigin}/v1/planning`, { method: "POST" }));
    expect(response.status).toBe(400);
    expect(fetchMock.mock.calls[0][1]?.body).toEqual(new Uint8Array());
  });

  it("bounds slow request reads and does not wait for a stalled cancel hook", async () => {
    vi.useFakeTimers();
    const cancel = vi.fn(() => new Promise<void>(() => undefined));
    const pending = POST(streamingPost(new ReadableStream({ cancel })));
    await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS);
    await expectSafeFailure(await pending, 503, "unavailable");
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels request reads when the caller disconnects, without surfacing its reason", async () => {
    const controller = new AbortController();
    const cancel = vi.fn();
    const pending = POST(streamingPost(new ReadableStream({ cancel }), {}, controller.signal));
    controller.abort(PRIVATE_SENTINEL);
    await expectSafeFailure(await pending, 503, "unavailable");
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("server-only Service loading and configuration", () => {
  it("fetches only the fixed direct Django navigation endpoint without caching", async () => {
    fetchMock.mockResolvedValue(jsonResponse({ services }));
    expect(await getServices()).toEqual({ ok: true, services });
    expectPrivateUpstream("services");
  });

  it.each([400, 401, 403, 404, 413, 422, 429, 500, 502, 503, 599])("catches and sanitizes navigation HTTP %i", async (status) => {
    fetchMock.mockResolvedValue(new Response(PRIVATE_SENTINEL, { status }));
    expect(await getServices()).toEqual({ ok: false, kind: status === 429 ? "rate_limited" : "unavailable" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each([
    () => jsonResponse({ services: [{ ...services[0], facts: input.facts }] }),
    () => jsonResponse({ services: [{ ...services[0], title: { ...services[0].title, private: PRIVATE_SENTINEL } }] }),
    () => jsonResponse({ services, candidates: [PRIVATE_SENTINEL] }),
    () => jsonResponse({ services: "wrong" }),
    () => new Response(`{"services":${PRIVATE_SENTINEL}`, { headers: { "Content-Type": "application/json" } }),
    () => new Response(`<html>${PRIVATE_SENTINEL}</html>`),
  ])("catches malformed navigation without rendering or reporting its details %#", async (response) => {
    fetchMock.mockImplementation(async () => response());
    expect(await getServices()).toEqual({ ok: false, kind: "unavailable" });
    await expectSafeFailure(await GET(get()), 502, "unexpected_response");
  });

  it("catches all direct Service transport errors", async () => {
    fetchMock.mockRejectedValue(new Error(PRIVATE_SENTINEL));
    expect(await getServices()).toEqual({ ok: false, kind: "unavailable" });
  });

  it.each([undefined, "", `not-a-url-${PRIVATE_SENTINEL}`, `https://user:${PRIVATE_SENTINEL}@django.internal`, `file:///${PRIVATE_SENTINEL}`, `https://django.internal/${PRIVATE_SENTINEL}`, `https://django.internal?secret=${PRIVATE_SENTINEL}`, `https://django.internal#${PRIVATE_SENTINEL}`])(
    "fails closed on missing or invalid production configuration %#", async (origin) => {
      vi.stubEnv("BARDI_API_ORIGIN", origin);
      expect(await getServices()).toEqual({ ok: false, kind: "unavailable" });
      await expectSafeFailure(await GET(get()), 503, "unavailable");
      await expectSafeFailure(await POST(post()), 503, "unavailable");
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it("uses localhost only in development with no configured origin", async () => {
    vi.stubEnv("BARDI_API_ORIGIN", undefined);
    vi.stubEnv("NODE_ENV", "development");
    fetchMock.mockResolvedValue(jsonResponse({ services }));
    expect(await getServices()).toEqual({ ok: true, services });
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/v1/services");
  });

  it("does not use a public environment variable or silently default outside development", async () => {
    vi.stubEnv("NODE_ENV", "test");
    vi.stubEnv("BARDI_API_ORIGIN", undefined);
    vi.stubEnv("NEXT_PUBLIC_BARDI_API_ORIGIN", `https://attacker.example/${PRIVATE_SENTINEL}`);
    expect(await getServices()).toEqual({ ok: false, kind: "unavailable" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("times out both handlers and direct navigation even if fetch never settles", async () => {
    vi.useFakeTimers();
    fetchMock.mockReturnValue(new Promise(() => undefined));
    const navigation = getServices();
    const getResponse = GET(get());
    const postResponse = POST(post());
    await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS);
    expect(await navigation).toEqual({ ok: false, kind: "unavailable" });
    await expectSafeFailure(await getResponse, 503, "unavailable");
    await expectSafeFailure(await postResponse, 503, "unavailable");
    for (const [, options] of fetchMock.mock.calls) expect(options?.signal?.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("includes slow upstream response bodies in the deadline", async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation(async () => new Response(new ReadableStream(), {
      headers: { "Content-Type": "application/json" },
    }));
    const navigation = getServices();
    const planning = POST(post());
    await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS);
    expect(await navigation).toEqual({ ok: false, kind: "unavailable" });
    await expectSafeFailure(await planning, 503, "unavailable");
    expect(vi.getTimerCount()).toBe(0);
  });

  it("cancels pending upstream calls on disconnect instead of leaking abort reasons", async () => {
    const controller = new AbortController();
    fetchMock.mockReturnValue(new Promise(() => undefined));
    const pending = GET(get({}, controller.signal));
    controller.abort(new Error(PRIVATE_SENTINEL));
    await expectSafeFailure(await pending, 503, "unavailable");
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true);
  });

  it("does not fetch for an already disconnected caller and releases successful deadlines", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    controller.abort(PRIVATE_SENTINEL);
    await expectSafeFailure(await POST(post({}, controller.signal)), 503, "unavailable");
    await expectSafeFailure(await GET(get({}, controller.signal)), 503, "unavailable");
    expect(fetchMock).not.toHaveBeenCalled();
    fetchMock.mockResolvedValue(jsonResponse({ services }));
    expect(await getServices()).toEqual({ ok: true, services });
    expect(vi.getTimerCount()).toBe(0);
  });
});
