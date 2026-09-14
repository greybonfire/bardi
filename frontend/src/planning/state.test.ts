// @vitest-environment node
import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";
import type { Facts, PlanningResult } from "@/api/contract";
import { answerLabel, enumLabels, fieldLabel, fieldLabels } from "./labels";
import { correctDiagnostics, diagnosticDate, diagnosticKeys, freshCase, isCalendarDate, isFacts, localToday, prefill, questionProblem, rewindCase, submitAnswers } from "./state";
import type { ActiveCase, Draft } from "./state";
import { answer, question, service } from "./test-fixtures";

const empty = () => freshCase(service.id, "2026-09-01");
function submitted(active: ActiveCase, q: ReturnType<typeof question>, draft: Draft) {
  const result = submitAnswers(active, q, draft);
  if (!("active" in result)) throw new Error("Expected valid test answers");
  return result.active;
}

describe("calendar and transport boundaries", () => {
  it("uses local Gregorian components, never a UTC ISO slice", () => {
    const now = new Date("2026-09-01T00:30:00Z");
    vi.spyOn(now, "getFullYear").mockReturnValue(2026);
    vi.spyOn(now, "getMonth").mockReturnValue(7);
    vi.spyOn(now, "getDate").mockReturnValue(31);
    vi.spyOn(now, "toISOString").mockImplementation(() => { throw new Error("UTC not allowed"); });
    expect(localToday(now)).toBe("2026-08-31");
  });
  it.each(["0001-01-01", "2000-02-29", "2024-02-29", "9999-12-31"])("accepts canonical date %s", (date) => expect(isCalendarDate(date)).toBe(true));
  it.each(["0000-01-01", "1900-02-29", "2026-02-29", "2026-04-31", "2026-1-01", "2026-01-1", "2026-00-01", "2026-13-01", "2026-09-01T00:00:00Z", "٢٠٢٦-٠٩-٠١", ""])("rejects date %s", (date) => expect(isCalendarDate(date)).toBe(false));
  it("counts Unicode code points and permits all transport key spellings safely", () => {
    const special: Facts = JSON.parse('{"__proto__":"source value","constructor":false,"toString":0,"":""}');
    expect(isFacts(special)).toBe(true);
    expect(isFacts({ ["𓀀".repeat(128)]: "𓀀".repeat(2048) })).toBe(true);
    expect(isFacts({ ["𓀀".repeat(129)]: "ok" })).toBe(false);
    expect(isFacts({ value: "𓀀".repeat(2049) })).toBe(false);
    expect(isFacts(Object.fromEntries(Array.from({ length: 128 }, (_, i) => [`k${i}`, true])))).toBe(true);
    expect(isFacts(Object.fromEntries(Array.from({ length: 129 }, (_, i) => [`k${i}`, true])))).toBe(false);
  });
  it.each([null, [], { a: null }, { a: [] }, { a: {} }, { a: 1.2 }, { a: NaN }, { a: Infinity }, { a: 9007199254740992 }])("rejects invalid transport without coercion (%j)", (facts) => expect(isFacts(facts)).toBe(false));
});

describe("typed answers", () => {
  it("starts with no facts and no implicit false, null, or selection", () => {
    expect(empty().facts).toEqual({});
    expect(prefill(question(), {})).toEqual({});
    expect(submitAnswers(empty(), question(), {})).toEqual({ errors: { fields: {}, form: "required" } });
  });
  it.each([true, false])("submits boolean %s as a boolean", (value) => {
    expect(submitted(empty(), question(), { father_alive: value }).facts).toEqual({ father_alive: value });
  });
  it.each(["false", "true", "0", 0, null])("does not coerce boolean %j", (value) => {
    expect(submitAnswers(empty(), question(), { father_alive: value } as Draft)).toMatchObject({ errors: { fields: { father_alive: "boolean" } } });
  });
  it("preserves exact enum values, strings including whitespace, dates, and safe integers", () => {
    const q = question("all", [answer("e", "enum", { enum_options: ["future/value"] }), answer("s", "string"), answer("d", "date"), answer("i", "integer", { minimum: 0 }), answer("b", "boolean")]);
    const active = submitted(empty(), q, { e: "future/value", s: "  مصر  ", d: "2000-02-29", i: "9007199254740991", b: false });
    expect(active.facts).toEqual({ e: "future/value", s: "  مصر  ", d: "2000-02-29", i: 9007199254740991, b: false });
    expect(prefill(q, active.facts)).toEqual({ e: "future/value", s: "  مصر  ", d: "2000-02-29", i: "9007199254740991", b: false });
  });
  it.each(["", " ", "1.0", "1e2", "+2", "٢", "9007199254740992", "Infinity", true])("rejects noninteger draft %j", (value) => {
    expect(submitAnswers(empty(), question("i", [answer("i", "integer")]), { i: value })).toMatchObject({ errors: { fields: { i: "integer" } } });
  });
  it("checks the minimum and preserves zero", () => {
    const q = question("i", [answer("i", "integer", { minimum: 0 })]);
    expect(submitAnswers(empty(), q, { i: "-1" })).toMatchObject({ errors: { fields: { i: "minimum" } } });
    expect(submitted(empty(), q, { i: "0" }).facts).toEqual({ i: 0 });
  });
  it("distinguishes omitted and explicitly empty text, without a UTF-16 maxlength", () => {
    const q = question("s", [answer("s", "string")]);
    expect(submitAnswers(empty(), q, {})).toHaveProperty("errors.form", "required");
    expect(submitted(empty(), q, { s: "" }).facts).toEqual({ s: "" });
    expect(submitted(empty(), q, { s: "𓀀".repeat(2048) }).facts.s).toBe("𓀀".repeat(2048));
    expect(submitAnswers(empty(), q, { s: "𓀀".repeat(2049) })).toHaveProperty("errors.fields.s", "string");
  });
  it("rejects enum approximations and noncanonical dates", () => {
    const q = question("q", [answer("e", "enum", { enum_options: ["yes"] }), answer("d", "date")]);
    expect(submitAnswers(empty(), q, { e: "YES", d: "2026-02-30" })).toMatchObject({ errors: { fields: { e: "enum", d: "date" } } });
  });
  it("uses only the returned answer keys, including prototype-shaped keys", () => {
    const q = question("special", [answer("__proto__", "string"), answer("constructor", "boolean")]);
    const active = submitted(empty(), q, JSON.parse('{"__proto__":"not a prototype","constructor":false,"extra":"ignored"}'));
    expect(Object.keys(active.facts)).toEqual(["__proto__", "constructor"]);
    expect(active.facts.__proto__).toBe("not a prototype");
    expect(Object.getPrototypeOf(active.facts)).toBe(Object.prototype);
    expect({}).not.toHaveProperty("polluted");
  });
  it("refuses to cross the fact-count limit", () => {
    const active = { ...empty(), facts: Object.fromEntries(Array.from({ length: 128 }, (_, i) => [`k${i}`, true])) };
    expect(submitAnswers(active, question(), { father_alive: true })).toHaveProperty("errors.form", "limits");
  });
});

describe("correction history and recurrence", () => {
  const multi = question("q.multi", [answer("father_alive", "boolean"), answer("other_living_sons_of_father_count", "integer", { minimum: 0 })]);
  const middle = question("q.middle", [answer("middle", "string")]);
  it("prefills a recurring multi-Fact question and submits only answered fields", () => {
    const first = submitted(empty(), multi, { father_alive: false });
    expect(first.facts).toEqual({ father_alive: false });
    expect(questionProblem(multi, first.facts)).toBe(false);
    const second = submitted(first, multi, { ...prefill(multi, first.facts), other_living_sons_of_father_count: "0" });
    expect(second.facts).toEqual({ father_alive: false, other_living_sons_of_father_count: 0 });
    expect(questionProblem(multi, second.facts)).toBe(true);
  });
  it("prevents unchanged partial answers from looping", () => {
    const first = submitted(empty(), multi, { father_alive: false });
    expect(submitAnswers(first, multi, prefill(multi, first.facts))).toHaveProperty("errors.form", "unchanged");
  });
  it("rewinds the targeted group and all later facts, leaving earlier groups intact", () => {
    let active = submitted(empty(), middle, { middle: "keep" });
    active = submitted(active, multi, { father_alive: true });
    active = submitted(active, question("q.later", [answer("later", "boolean")]), { later: false });
    expect(rewindCase(active, 1)).toEqual({ ...active, facts: { middle: "keep" }, history: active.history.slice(0, 1) });
    expect(rewindCase(active, -1)).toBe(active);
  });
  it("changing or omitting a prefilled multi-field value clears stale intermediate branches", () => {
    let active = submitted(empty(), multi, { father_alive: true });
    active = submitted(active, middle, { middle: "stale" });
    const omitted = submitted(active, multi, { other_living_sons_of_father_count: "2" });
    expect(omitted.facts).toEqual({ other_living_sons_of_father_count: 2 });
    expect(omitted.history).toEqual([{ questionId: multi.id, keys: multi.answers.map(({ key }) => key) }]);
    const changed = submitted(active, multi, { father_alive: false, other_living_sons_of_father_count: "2" });
    expect(changed.facts).toEqual({ father_alive: false, other_living_sons_of_father_count: 2 });
  });
  it("diagnostics use the earliest matching history, not diagnostic order, and remove unknown targets", () => {
    let active = submitted(empty(), multi, { father_alive: true });
    active = submitted(active, middle, { middle: "remove" });
    active = submitted(active, multi, { father_alive: true, other_living_sons_of_father_count: "0" });
    active.facts = { ...active.facts, untracked: false };
    const result: Extract<PlanningResult, { type: "invalid" }> = { type: "invalid", diagnostics: [
      { code: "contradictory_facts", path: ["facts", "middle"] },
      { code: "contradictory_facts", path: ["body", "facts", "other_living_sons_of_father_count"] },
      { code: "invalid_fact_value", path: ["facts", "untracked"] },
      { code: "invalid_request", path: ["body", "evaluation_context", "evaluation_date"] },
      { code: "invalid_request", path: ["facts", 2] },
    ] };
    expect(diagnosticDate(result)).toBe(true);
    expect(diagnosticKeys(result)).toEqual(["middle", "other_living_sons_of_father_count", "untracked"]);
    expect(correctDiagnostics(active, diagnosticKeys(result))).toMatchObject({ facts: {}, history: [] });
  });
  it("safely removes an unknown targeted fact without guessing a question", () => {
    const active = { ...empty(), facts: JSON.parse('{"__proto__":true,"keep":false}') as Facts };
    expect(correctDiagnostics(active, ["__proto__"]).facts).toEqual({ keep: false });
  });
  it("rejects unrenderable, duplicate, or fully answered Questions as a recovery state", () => {
    expect(questionProblem(question("empty", []), {})).toBe(true);
    expect(questionProblem(question("dup", [answer("k", "boolean"), answer("k", "integer")]), {})).toBe(true);
    expect(questionProblem(question("enum", [answer("k", "enum")]), {})).toBe(true);
    expect(questionProblem(question("long", [answer("x".repeat(129), "string")]), {})).toBe(true);
    expect(questionProblem(question(), { father_alive: false })).toBe(true);
  });
});

describe("bilingual presentation mappings", () => {
  it("covers every current source Fact and enum option in the authoritative registry", () => {
    const source = readFileSync(new URL("../../../backend/planning/facts.py", import.meta.url), "utf8");
    const registry = source.split("_FACT_DEFINITIONS = {")[1].split("\n}\n")[0];
    const definitions = registry.split(/(?=^    "[^"]+": FactDefinition)/m).filter((block) => block.includes("FactDefinition"));
    expect(definitions.length).toBeGreaterThan(30);
    for (const definition of definitions) {
      if (definition.includes("derived=True")) continue;
      const key = definition.match(/^\s*"([^"]+)"/)![1];
      expect(Object.hasOwn(fieldLabels, key), key).toBe(true);
      for (const locale of ["ar", "en"] as const) expect(fieldLabel(key, locale), key).not.toBe(key);
      const options = definition.match(/"enum",\s*\(([^)]*)\)/)?.[1].matchAll(/"([^"]+)"/g);
      if (options) {
        for (const [, value] of options) {
          expect(Object.hasOwn(enumLabels[key], value), `${key}:${value}`).toBe(true);
          expect(answerLabel(key, value, "ar")).not.toBe(value);
          expect(answerLabel(key, value, "en")).not.toBe(value);
        }
      }
    }
  });
  it("does not guess future option/key labels or use inherited mapping properties", () => {
    expect(answerLabel("citizenship", "future/value", "ar")).toBe("future/value");
    expect(answerLabel("constructor", "__proto__", "en")).toBe("__proto__");
    expect(fieldLabel("toString", "ar")).toBe("toString");
    expect(answerLabel("father_alive", false, "ar")).toBe("لأ");
  });
});
