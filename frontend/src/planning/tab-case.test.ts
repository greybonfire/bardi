import { beforeEach, describe, expect, it, vi } from "vitest";
import { CASE_STORAGE_KEY } from "./storage";
import { freshCase } from "./state";
import { attachTabCase, createTabCaseOwner } from "./tab-case";

beforeEach(() => sessionStorage.clear());

describe("browser-only tab case ownership", () => {
  it("shares the lazy singleton across route attachments without retaining results", () => {
    const first = attachTabCase("test.service", vi.fn());
    first.state.active = { ...first.state.active, facts: { test_answer: false } };
    first.release();
    const second = attachTabCase("test.service", vi.fn());
    expect(second.state).toBe(first.state);
    expect(second.state.active.facts).toEqual({ test_answer: false });
    expect(Object.keys(second.state).sort()).toEqual(["active", "failure", "idle", "notice", "retryUntil", "storage"]);
    second.release();
  });

  it("invalidates an old attachment before it can cancel or overwrite a newer one", () => {
    const attach = createTabCaseOwner();
    const oldCancel = vi.fn();
    const newCancel = vi.fn();
    const old = attach("test.service", oldCancel);
    const current = attach("test.service", newCancel);
    expect(oldCancel).toHaveBeenCalledOnce();
    expect(old.isCurrent()).toBe(false);
    expect(current.isCurrent()).toBe(true);
    old.release();
    expect(current.isCurrent()).toBe(true);
    expect(newCancel).not.toHaveBeenCalled();
    current.release();
    expect(current.isCurrent()).toBe(false);
    expect(newCancel).toHaveBeenCalledOnce();
  });

  it("does not reload stale storage or write a cleared idle case on reattachment", () => {
    const attach = createTabCaseOwner();
    const first = attach("test.service", vi.fn());
    first.state.active = freshCase("test.service");
    first.state.idle = true;
    first.state.failure = "rate_limited";
    first.state.retryUntil = Date.now() + 30_000;
    first.state.storage.clear();
    first.release();
    const get = vi.spyOn(Storage.prototype, "getItem");
    const set = vi.spyOn(Storage.prototype, "setItem");
    const next = attach("test.service", vi.fn());
    expect(get).not.toHaveBeenCalled();
    expect(set).not.toHaveBeenCalled();
    expect(next.state).toBe(first.state);
    expect(next.state.idle).toBe(true);
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    expect(next.state.retryUntil).toBe(first.state.retryUntil);
  });

  it("a different Service replaces the only case, even without session storage", () => {
    vi.spyOn(window, "sessionStorage", "get").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    const attach = createTabCaseOwner();
    const first = attach("test.first", vi.fn());
    first.state.active.facts = { test_answer: false };
    first.state.idle = true;
    const other = attach("test.other", vi.fn());
    expect(other.state.active.facts).toEqual({});
    expect(other.state.idle).toBe(false);
    const returned = attach("test.first", vi.fn());
    expect(returned.state).not.toBe(first.state);
    expect(returned.state.active.facts).toEqual({});
    expect(returned.state.notice).toBe("memory");
  });

  it("a new document restores source data, not the old document's recovery markers", () => {
    const first = createTabCaseOwner()("test.service", vi.fn());
    const source = { ...first.state.active, facts: { test_answer: false } };
    first.state.storage.save(source);
    first.state.failure = "rate_limited";
    first.state.retryUntil = Date.now() + 30_000;
    first.release();
    const reloaded = createTabCaseOwner()("test.service", vi.fn());
    expect(reloaded.state.active).toEqual(source);
    expect(reloaded.state.notice).toBe("restored");
    expect(reloaded.state.failure).toBeNull();
    expect(reloaded.state.retryUntil).toBe(0);
    expect(Object.keys(JSON.parse(sessionStorage.getItem(CASE_STORAGE_KEY)!)).sort()).toEqual(["date", "facts", "history", "serviceId", "version"]);
  });
});
