import { beforeEach, describe, expect, it, vi } from "vitest";
import { createTabCaseOwner } from "./tab-case";
import { CASE_STORAGE_KEY } from "./storage";
import { freshCase } from "./state";

beforeEach(() => sessionStorage.clear());

describe("service-independent case deletion", () => {
  it("deletes an unopened retired or corrupt case without reading it or touching unrelated storage", () => {
    sessionStorage.setItem(CASE_STORAGE_KEY, "TEST-ONLY corrupt retired case");
    sessionStorage.setItem("unrelated", "keep");
    const attach = createTabCaseOwner();
    const read = vi.spyOn(Storage.prototype, "getItem");
    const write = vi.spyOn(Storage.prototype, "setItem");
    expect(attach.clear()).toBe(true);
    expect(read).not.toHaveBeenCalled();
    expect(write).not.toHaveBeenCalled();
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    expect(sessionStorage.getItem("unrelated")).toBe("keep");
    const next = attach("test.service", vi.fn());
    expect(next.state.active.facts).toEqual({});
    expect(next.state.idle).toBe(true);
    expect(write).not.toHaveBeenCalled();
  });

  it("invalidates the old owner before cancelling and keeps an empty idle case across reattachments", () => {
    const attach = createTabCaseOwner();
    const cancel = vi.fn(() => { expect(old.isCurrent()).toBe(false); });
    const old = attach("test.service", cancel);
    old.state.active = { ...old.state.active, facts: { test_answer: false }, history: [{ questionId: "q", keys: ["test_answer"] }] };
    old.state.storage.save(old.state.active);
    old.state.failure = "rate_limited";
    old.state.retryUntil = Date.now() + 30_000;
    const deadline = old.state.retryUntil;
    expect(attach.clear()).toBe(true);
    expect(cancel).toHaveBeenCalledOnce();
    expect(old.state.active.facts).toEqual({});
    expect(old.state.active.history).toEqual([]);
    expect(old.state.idle).toBe(true);
    expect(old.state.retryUntil).toBe(deadline);
    const nextCancel = vi.fn();
    const next = attach("test.service", nextCancel);
    expect(next.state).toBe(old.state);
    expect(next.state.idle).toBe(true);
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    old.release();
    expect(next.isCurrent()).toBe(true);
    expect(nextCancel).not.toHaveBeenCalled();
    next.release();
  });

  it("cannot restore stale disk answers after deletion fails, including after Service changes", () => {
    const stale = { ...freshCase("test.old"), facts: { test_answer: false } };
    sessionStorage.setItem(CASE_STORAGE_KEY, JSON.stringify(stale));
    const attach = createTabCaseOwner();
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("TEST-ONLY", "SecurityError"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("TEST-ONLY", "QuotaExceededError"); });
    const read = vi.spyOn(Storage.prototype, "getItem");
    expect(attach.clear()).toBe(false);
    for (const serviceId of ["test.old", "test.other", "test.old"]) {
      const next = attach(serviceId, vi.fn());
      expect(next.state.active.facts).toEqual({});
      expect(["memory", "clear_failed"]).toContain(next.state.notice);
      next.release();
    }
    expect(read).not.toHaveBeenCalled();
  });

  it("clears in-memory data and invalidates pending work even when sessionStorage is inaccessible", () => {
    vi.spyOn(window, "sessionStorage", "get").mockImplementation(() => { throw new DOMException("TEST-ONLY", "SecurityError"); });
    const attach = createTabCaseOwner();
    const cancel = vi.fn();
    const old = attach("test.service", cancel);
    old.state.active.facts = { test_answer: true };
    expect(attach.clear()).toBe(false);
    expect(cancel).toHaveBeenCalledOnce();
    expect(old.isCurrent()).toBe(false);
    expect(old.state.active.facts).toEqual({});
    const next = attach("test.service", vi.fn());
    expect(next.state.idle).toBe(true);
    expect(next.state.notice).toBe("clear_failed");
  });
});
