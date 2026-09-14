// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, PLANNING_REQUEST_TIMEOUT_MS, requestPlan } from "./client";
import { input, invalid, jsonResponse, plan, PRIVATE_SENTINEL } from "./test-fixtures";

const fetchMock = vi.fn<typeof fetch>();
beforeEach(() => {
  vi.useFakeTimers();
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  for (const method of ["debug", "error", "info", "log", "trace", "warn"] as const) {
    vi.spyOn(console, method).mockImplementation(() => undefined);
  }
});
afterEach(() => {
  expect(vi.getTimerCount()).toBe(0);
  for (const method of ["debug", "error", "info", "log", "trace", "warn"] as const) {
    expect(console[method]).not.toHaveBeenCalled();
  }
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
const caught = (pending: Promise<unknown>) => pending.catch((error: unknown) => error);

function expectTimeout(error: unknown, parent: AbortController) {
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({ name: "ApiError", kind: "network", retryAfter: null });
  expect(parent.signal.aborted).toBe(false);
  expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true);
  if (!(error instanceof ApiError)) throw new Error("Expected sanitized timeout");
  expect(JSON.stringify(Object.fromEntries(Object.getOwnPropertyNames(error).map((key) =>
    [key, (error as unknown as Record<string, unknown>)[key]])))).not.toContain(PRIVATE_SENTINEL);
  expect(error).not.toHaveProperty("cause");
}

describe("browser planning deadline", () => {
  it("bounds a never-settling fetch without aborting the caller or automatically retrying", async () => {
    expect(PLANNING_REQUEST_TIMEOUT_MS).toBe(20_000);
    fetchMock.mockReturnValue(new Promise(() => undefined));
    const parent = new AbortController();
    let settled = false;
    const pending = caught(requestPlan(input, parent.signal)).then((value) => { settled = true; return value; });
    await vi.advanceTimersByTimeAsync(19_999);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    expectTimeout(await pending, parent);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("uses one deadline for fetch plus response-body consumption, not a fresh body budget", async () => {
    let headers!: (response: Response) => void;
    fetchMock.mockReturnValue(new Promise((resolve) => { headers = resolve; }));
    const parent = new AbortController();
    const pending = caught(requestPlan(input, parent.signal));
    await vi.advanceTimersByTimeAsync(19_000);
    const response = jsonResponse(plan);
    const read = vi.spyOn(response, "json").mockReturnValue(new Promise(() => undefined));
    headers(response);
    await vi.advanceTimersByTimeAsync(0);
    expect(read).toHaveBeenCalledOnce();
    await vi.advanceTimersByTimeAsync(1_000);
    expectTimeout(await pending, parent);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("ignores late completion and permits a fresh manual request with unchanged answers", async () => {
    let finish!: (response: Response) => void;
    fetchMock.mockReturnValueOnce(new Promise((resolve) => { finish = resolve; }));
    const parent = new AbortController();
    const pending = caught(requestPlan(input, parent.signal));
    await vi.advanceTimersByTimeAsync(PLANNING_REQUEST_TIMEOUT_MS);
    const error = await pending;
    expectTimeout(error, parent);
    finish(jsonResponse(plan));
    await vi.advanceTimersByTimeAsync(0);
    expect(await pending).toBe(error);
    fetchMock.mockResolvedValueOnce(jsonResponse(plan));
    expect(await requestPlan(input, parent.signal)).toEqual(plan);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[1][1]?.body).toBe(JSON.stringify(input));
    expect(fetchMock.mock.calls[1][1]?.signal?.aborted).toBe(false);
  });

  it.each(["fetch", "body"])("keeps intentional cancellation silent during %s and releases its deadline", async (stage) => {
    if (stage === "fetch") fetchMock.mockReturnValue(new Promise(() => undefined));
    else {
      const response = jsonResponse(plan);
      vi.spyOn(response, "json").mockReturnValue(new Promise(() => undefined));
      fetchMock.mockResolvedValue(response);
    }
    const parent = new AbortController();
    const pending = caught(requestPlan(input, parent.signal));
    await vi.advanceTimersByTimeAsync(19_999);
    parent.abort(new Error(PRIVATE_SENTINEL));
    expect(await pending).toMatchObject({ name: "AbortError", message: "Request cancelled." });
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each([200, 400, 422, 429, 503])("removes the timer and parent listener after HTTP %i", async (status) => {
    const parent = new AbortController();
    const add = vi.spyOn(parent.signal, "addEventListener");
    const remove = vi.spyOn(parent.signal, "removeEventListener");
    fetchMock.mockResolvedValue(jsonResponse(status === 200 ? plan : invalid, status));
    await caught(requestPlan(input, parent.signal));
    const listener = add.mock.calls.find(([type]) => type === "abort")![1];
    expect(remove).toHaveBeenCalledWith("abort", listener);
    const transport = fetchMock.mock.calls[0][1]?.signal;
    parent.abort();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(transport?.aborted).toBe(false);
  });

  it("does not allocate a deadline or fetch for an already cancelled caller", async () => {
    const parent = new AbortController();
    parent.abort(PRIVATE_SENTINEL);
    expect(await caught(requestPlan(input, parent.signal))).toMatchObject({ name: "AbortError" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
