// @vitest-environment node
import { describe, expect, it } from "vitest";
import schemaSnapshot from "../../api-schema.json";
import {
  apiSchemas, calendarDateSchema, factsSchema, planningRequestSchema,
  planningResultSchema, servicesSchema, transportPlanningRequestSchema,
} from "./contract";
import { input, plan, PRIVATE_SENTINEL, results, services } from "./test-fixtures";

function withPrivateFields(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value.flatMap((item, index) => withPrivateFields(item).map((changed) =>
      value.map((original, position) => position === index ? changed : original)));
  }
  if (value === null || typeof value !== "object") return [];
  return [
    { ...value, internal_evidence: PRIVATE_SENTINEL },
    ...Object.entries(value).flatMap(([key, item]) =>
      withPrivateFields(item).map((changed) => ({ ...value, [key]: changed }))),
  ];
}

describe("public contract", () => {
  it.each(results)("accepts the complete $type result without changing it", (result) => {
    expect(planningResultSchema.parse(result)).toEqual(result);
    for (const extra of withPrivateFields(result)) {
      expect(planningResultSchema.safeParse(extra).success).toBe(false);
    }
  });

  it("whitelists navigation at every level", () => {
    expect(servicesSchema.parse({ services })).toEqual({ services });
    for (const extra of withPrivateFields({ services })) {
      expect(servicesSchema.safeParse(extra).success).toBe(false);
    }
  });

  it("keeps the snapshot limited to the two public operations and checks all generated schemas", () => {
    expect(Object.keys(schemaSnapshot.paths).sort()).toEqual(["/v1/planning", "/v1/services"]);
    expect(Object.keys(apiSchemas).sort()).toEqual(Object.keys(schemaSnapshot.components.schemas).sort());
    expect(Object.keys(schemaSnapshot.paths["/v1/planning"])).toEqual(["post"]);
    expect(Object.keys(schemaSnapshot.paths["/v1/services"])).toEqual(["get"]);
  });

  it.each([
    null, [], {}, { type: "unknown" }, { ...plan, routing: undefined },
    { ...plan, inconclusive_sections: ["fees"] },
    { ...plan, fees: [{ ...plan.fees[0], amount: "100" }] },
    { ...plan, checklist_items: [{ ...plan.checklist_items[0], quantity: 1.5 }] },
    { type: "invalid", diagnostics: [{ code: "error", path: [null] }] },
    { type: "next_question", service_id: "x", question: { id: "q", text: "?", answers: [{ key: "x", kind: "float", enum_options: [], minimum: null }] } },
  ])("rejects malformed, incomplete, and coerced results %#", (result) => {
    expect(planningResultSchema.safeParse(result).success).toBe(false);
  });

  it("models null wire Facts separately from the form's omitted answers", () => {
    expect(planningRequestSchema.parse(input)).toEqual(input);
    expect(transportPlanningRequestSchema.parse({ ...input, facts: { unknown: null } }).facts)
      .toEqual({ unknown: null });
    expect(planningRequestSchema.safeParse({ ...input, facts: { unknown: null } }).success).toBe(false);
    expect(factsSchema.parse({})).toEqual({});
  });

  it("counts transport string limits in Unicode code points, without inventing key restrictions", () => {
    const facts = { ["😀".repeat(128)]: "😀".repeat(2048), "": "" };
    expect(factsSchema.parse(facts)).toEqual(facts);
    expect(factsSchema.safeParse({ ["😀".repeat(129)]: true }).success).toBe(false);
    expect(factsSchema.safeParse({ key: "😀".repeat(2049) }).success).toBe(false);
    expect(factsSchema.safeParse(Object.fromEntries(Array.from({ length: 128 }, (_, i) => [i, i]))).success).toBe(true);
    expect(factsSchema.safeParse(Object.fromEntries(Array.from({ length: 129 }, (_, i) => [i, i]))).success).toBe(false);
    expect(planningRequestSchema.safeParse({ ...input, service_id: "😀".repeat(128) }).success).toBe(true);
  });

  it.each([
    { ...input, locale: "fr" }, { ...input, service_id: " \t\n" },
    { ...input, service_id: "s".repeat(129) },
    ...[1.5, [], {}, null].map((value) => ({ ...input, facts: { key: value } })),
    { ...input, extra: PRIVATE_SENTINEL },
    { ...input, evaluation_context: { ...input.evaluation_context, extra: PRIVATE_SENTINEL } },
  ])("rejects invalid or extra request transport fields %#", (value) => {
    expect(planningRequestSchema.safeParse(value).success).toBe(false);
  });

  it.each(["2026-9-01", "2026-02-29", "2026-04-31", "0000-01-01", "2026-09-01T00:00:00Z", "2026-09-01 "])(
    "requires canonical calendar dates: %s", (date) => {
      expect(calendarDateSchema.safeParse(date).success).toBe(false);
    },
  );
  it.each(["0001-01-01", "2024-02-29", "9999-12-31"])("accepts canonical calendar dates: %s", (date) => {
    expect(calendarDateSchema.parse(date)).toBe(date);
  });
});
