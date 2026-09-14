// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, requestPlan } from "./client";
import type { PlanningRequest } from "./contract";
import { input, invalid, jsonResponse, PRIVATE_SENTINEL, results } from "./test-fixtures";

const fetchMock = vi.fn<typeof fetch>();
const logMethods = ["debug", "error", "info", "log", "trace", "warn"] as const;
beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  for (const method of logMethods) vi.spyOn(console, method).mockImplementation(() => undefined);
});
afterEach(() => {
  for (const method of logMethods) expect(console[method]).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});
const signal = () => new AbortController().signal;

async function expectSafeError(pending: Promise<unknown>, kind: string, retryAfter: number | null = null) {
  const error: unknown = await pending.catch((caught: unknown) => caught);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ name: "ApiError", kind, retryAfter });
  const properties = Object.fromEntries(Object.getOwnPropertyNames(error).map((key) =>
    [key, (error as unknown as Record<string, unknown>)[key]]));
  expect(JSON.stringify(properties)).not.toContain(PRIVATE_SENTINEL);
  expect(properties).not.toHaveProperty("cause");
  expect(fetchMock).toHaveBeenCalledTimes(1);
}

describe("requestPlan", () => {
  it.each(results)("returns parsed $type from a private same-origin POST", async (result) => {
    fetchMock.mockResolvedValue(jsonResponse(result));
    const abortSignal = signal();
    expect(await requestPlan(input, abortSignal)).toEqual(result);
    expect(fetchMock).toHaveBeenCalledExactlyOnceWith("/v1/planning", {
      method: "POST", headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(input), signal: expect.any(AbortSignal), credentials: "omit", cache: "no-store",
      referrerPolicy: "no-referrer", redirect: "error",
    });
  });

  it.each([200, 400, 413, 422])("returns valid invalid diagnostics at HTTP %i", async (status) => {
    fetchMock.mockResolvedValue(jsonResponse(invalid, status));
    expect(await requestPlan(input, signal())).toEqual(invalid);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each([400, 413, 422])("does not accept another discriminator at HTTP %i", async (status) => {
    fetchMock.mockResolvedValue(jsonResponse(results[0], status));
    await expectSafeError(requestPlan(input, signal()), "unexpected_response");
  });

  it.each([500, 501, 502, 503, 504, 599])("maps HTTP %i to unavailable, never a domain result", async (status) => {
    fetchMock.mockResolvedValue(jsonResponse(invalid, status, { "Retry-After": "42" }));
    await expectSafeError(requestPlan(input, signal()), "unavailable", 42);
  });

  it.each([
    ["0", 0], ["17", 17], ["86400", 86400], ["99999", null], ["999999999999999", null],
    ["-1", null], ["1.5", null], ["Wed, 21 Oct 2030 07:28:00 GMT", null],
    [PRIVATE_SENTINEL, null], [null, null],
  ] as const)("sanitizes a 429 Retry-After of %s and never retries", async (value, expected) => {
    fetchMock.mockResolvedValue(new Response(PRIVATE_SENTINEL, {
      status: 429, headers: value === null ? {} : { "Retry-After": value },
    }));
    await expectSafeError(requestPlan(input, signal()), "rate_limited", expected);
  });

  it.each([201, 202, 204, 205, 206, 301, 302, 303, 304, 307, 308, 401, 403, 404, 405, 415, 418])(
    "rejects non-contract HTTP %i", async (status) => {
      fetchMock.mockResolvedValue(new Response(null, { status }));
      await expectSafeError(requestPlan(input, signal()), "unexpected_response");
    },
  );

  it.each([
    () => new Response(`{"type":${PRIVATE_SENTINEL}`, { headers: { "Content-Type": "application/json" } }),
    () => new Response(`<html>${PRIVATE_SENTINEL}</html>`, { headers: { "Content-Type": "text/html" } }),
    () => new Response(JSON.stringify(invalid)),
    () => jsonResponse(null), () => jsonResponse([]), () => jsonResponse({ type: "other" }),
    () => jsonResponse({ ...invalid, facts: input.facts }),
    () => jsonResponse({ type: "invalid", diagnostics: [{ code: "error", path: [], input: PRIVATE_SENTINEL }] }),
  ])("sanitizes malformed JSON, media types and whitelist failures %#", async (response) => {
    fetchMock.mockResolvedValue(response());
    await expectSafeError(requestPlan(input, signal()), "unexpected_response");
  });

  it("sanitizes transport errors without logging, retaining a cause, or retrying", async () => {
    fetchMock.mockRejectedValue(new TypeError(`https://secret@internal/${PRIVATE_SENTINEL}`));
    await expectSafeError(requestPlan(input, signal()), "network");
  });

  it("sanitizes response stream failures", async () => {
    fetchMock.mockResolvedValue(new Response(new ReadableStream({
      start(controller) { controller.error(new Error(PRIVATE_SENTINEL)); },
    }), { headers: { "Content-Type": "application/json" } }));
    await expectSafeError(requestPlan(input, signal()), "network");
  });

  it("allows Django to diagnose transport-invalid values instead of adding client rule semantics", async () => {
    fetchMock.mockResolvedValue(jsonResponse(invalid, 422));
    expect(await requestPlan({ ...input, facts: { key: 1.5 } }, signal())).toEqual(invalid);
    expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string).facts).toEqual({ key: 1.5 });
  });

  it("does not put serialization failures into exceptions", async () => {
    const facts: Record<string, unknown> = { value: PRIVATE_SENTINEL };
    facts.circular = facts;
    const error = await requestPlan({ ...input, facts } as PlanningRequest, signal()).catch((caught: unknown) => caught);
    expect(error).toMatchObject({ kind: "unexpected_response" });
    expect(String(error)).not.toContain(PRIVATE_SENTINEL);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("honors an already aborted signal without a POST or exposing its reason", async () => {
    const controller = new AbortController();
    controller.abort(new Error(PRIVATE_SENTINEL));
    await expect(requestPlan(input, controller.signal)).rejects.toMatchObject({ name: "AbortError", message: "Request cancelled." });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("preserves in-flight cancellation even if the transport does not settle", async () => {
    fetchMock.mockReturnValue(new Promise(() => undefined));
    const controller = new AbortController();
    const pending = requestPlan(input, controller.signal);
    controller.abort(PRIVATE_SENTINEL);
    await expect(pending).rejects.toMatchObject({ name: "AbortError", message: "Request cancelled." });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("preserves a transport AbortError without retaining its message", async () => {
    fetchMock.mockRejectedValue(new DOMException(PRIVATE_SENTINEL, "AbortError"));
    await expect(requestPlan(input, signal())).rejects.toMatchObject({ name: "AbortError", message: "Request cancelled." });
  });

  it("can cancel while consuming the response body", async () => {
    let started!: () => void;
    const reading = new Promise<void>((resolve) => { started = resolve; });
    fetchMock.mockResolvedValue(new Response(new ReadableStream({
      pull() { started(); },
    }), { headers: { "Content-Type": "application/json" } }));
    const controller = new AbortController();
    const pending = requestPlan(input, controller.signal);
    await reading;
    controller.abort(PRIVATE_SENTINEL);
    await expect(pending).rejects.toMatchObject({ name: "AbortError" });
  });
});
