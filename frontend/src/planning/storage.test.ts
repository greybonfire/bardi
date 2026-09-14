import { describe, expect, it } from "vitest";
import { freshCase } from "./state";
import { CASE_STORAGE_KEY, createCaseStorage, decodeCase } from "./storage";
import { service } from "./test-fixtures";

const saved = () => ({ ...freshCase(service.id, "2000-02-29"), facts: { father_alive: false }, history: [{ questionId: "q.father", keys: ["father_alive"] }] });
function storage() {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => { data.set(key, value); },
    removeItem: (key: string) => { data.delete(key); },
  };
}

describe("one versioned tab case", () => {
  it("restores source facts, date and minimal order without plans or locale-specific question text", () => {
    const tab = storage();
    const store = createCaseStorage(() => tab);
    expect(store.save(saved())).toBe(true);
    expect([...tab.data.keys()]).toEqual([CASE_STORAGE_KEY]);
    expect(store.load(service.id, "2026-09-01")).toEqual({ active: saved(), notice: "restored" });
    expect(tab.data.get(CASE_STORAGE_KEY)).not.toContain('"text"');
    expect(tab.data.get(CASE_STORAGE_KEY)).not.toContain('"plan"');
  });
  it("writes an explicit allow-list even if a caller supplies a wider runtime object", () => {
    const tab = storage();
    const active = { ...saved(), plan: { title: "not stored" }, derivedFacts: { only_son_candidate: true }, locale: "ar", history: [{ questionId: "q.father", keys: ["father_alive"], text: "old locale" }] };
    createCaseStorage(() => tab).save(active);
    expect(JSON.parse(tab.getItem(CASE_STORAGE_KEY)!)).toEqual(saved());
  });
  it("replaces rather than archives cases, and clears only its own key", () => {
    const tab = storage();
    tab.setItem("unrelated", "keep");
    const store = createCaseStorage(() => tab);
    store.save(saved());
    store.save(freshCase("service.other", "2026-09-01"));
    expect([...tab.data.keys()]).toHaveLength(2);
    store.clear();
    expect([...tab.data.entries()]).toEqual([["unrelated", "keep"]]);
  });
  it("removes a mismatched Service before opening a fresh case", () => {
    const tab = storage();
    const store = createCaseStorage(() => tab);
    store.save(saved());
    expect(store.load("service.other", "2026-09-01")).toEqual({ active: freshCase("service.other", "2026-09-01"), notice: "discarded" });
    expect(tab.getItem(CASE_STORAGE_KEY)).toBeNull();
  });
  it.each([
    "{", "null", "[]", "false",
    JSON.stringify({ ...saved(), version: 2 }),
    JSON.stringify({ ...saved(), plan: {} }),
    JSON.stringify({ ...saved(), date: "2026-02-30" }),
    JSON.stringify({ ...saved(), date: "2026-09-01T00:00:00Z" }),
    JSON.stringify({ ...saved(), facts: { father_alive: null } }),
    JSON.stringify({ ...saved(), facts: { father_alive: [] } }),
    JSON.stringify({ ...saved(), facts: { father_alive: 1.5 } }),
    JSON.stringify({ ...saved(), facts: { father_alive: 9007199254740992 } }),
    JSON.stringify({ ...saved(), facts: { ["𓀀".repeat(129)]: true } }),
    JSON.stringify({ ...saved(), facts: { text: "𓀀".repeat(2049) } }),
    JSON.stringify({ ...saved(), facts: Object.fromEntries(Array.from({ length: 129 }, (_, i) => [`k${i}`, true])) }),
    JSON.stringify({ ...saved(), history: [{ questionId: "q", keys: ["a", "a"] }] }),
    JSON.stringify({ ...saved(), history: [{ questionId: "q", keys: [] }] }),
    JSON.stringify({ ...saved(), history: [{ questionId: "q", keys: ["a"], text: "old locale" }] }),
    JSON.stringify({ ...saved(), history: Array.from({ length: 129 }, () => ({ questionId: "q", keys: ["a"] })) }),
  ])("rejects corrupt, incompatible or excessive restored data (%#)", (raw) => {
    expect(decodeCase(raw, service.id)).toBeNull();
    const tab = storage();
    tab.setItem(CASE_STORAGE_KEY, raw);
    const loaded = createCaseStorage(() => tab).load(service.id, "2026-09-01");
    expect(loaded.notice).toBe("discarded");
    expect(loaded.active.facts).toEqual({});
    expect(tab.getItem(CASE_STORAGE_KEY)).toBeNull();
  });
  it("accepts exact limits, empty text/keys, and own prototype-shaped keys without pollution", () => {
    const active = { ...saved(), facts: { ...JSON.parse('{"__proto__":false,"constructor":0,"":""}'), ["𓀀".repeat(128)]: "𓀀".repeat(2048) } };
    const restored = decodeCase(JSON.stringify(active), service.id)!;
    expect(Object.keys(restored.facts)).toHaveLength(4);
    expect(Object.hasOwn(restored.facts, "__proto__")).toBe(true);
    expect(restored.facts.__proto__).toBe(false);
    expect(Object.getPrototypeOf(restored.facts)).toBe(Object.prototype);
  });
  it("returns a notice instead of throwing when storage access is blocked", () => {
    const store = createCaseStorage(() => { throw new DOMException("blocked", "SecurityError"); });
    expect(store.load(service.id, "2026-09-01")).toEqual({ active: freshCase(service.id, "2026-09-01"), notice: "memory" });
    expect(store.save(saved())).toBe(false);
    expect(store.clear()).toBe(false);
  });
  it("removes an older case when a write hits quota, so refresh cannot revive stale branches", () => {
    const tab = storage();
    tab.setItem(CASE_STORAGE_KEY, JSON.stringify(saved()));
    const store = createCaseStorage(() => ({ ...tab, setItem() { throw new DOMException("quota", "QuotaExceededError"); } }));
    expect(store.save(freshCase(service.id))).toBe(false);
    expect(tab.getItem(CASE_STORAGE_KEY)).toBeNull();
  });
});
