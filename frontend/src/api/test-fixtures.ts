import type { Plan, PlanningRequest, PlanningResult, Service, Source } from "./contract";

export const PRIVATE_SENTINEL = "PRIVATE_FACT_DO_NOT_CAPTURE";
export const input: PlanningRequest = {
  service_id: "service.example",
  facts: { private_key: PRIVATE_SENTINEL, age: 30, has_document: false },
  locale: "ar",
  evaluation_context: { evaluation_date: "2026-09-01" },
};
export const services: Service[] = [{ id: "service.example", title: { ar: "خدمة", en: "Service" } }];
export const source: Source = {
  id: "source.example",
  authority_id: "authority.example",
  title: "Publication",
  locator: "https://example.org/publication",
  classification: "official",
  retrieved_on: "2026-08-01",
};
const guidance = {
  sources: [source],
  freshness: { state: "current", verified_on: "2026-08-01", reverify_on: null },
} as const;
// Keep this complete: empty arrays alone would not exercise nested whitelists.
export const plan: Plan = {
  type: "plan",
  service_id: "service.example",
  procedure_id: "procedure.example",
  procedure_version_id: "procedure.example.v1",
  title: "Localized plan",
  eligibility_bases: [{
    id: "basis.example", text: "Basis", checklist_item_ids: ["item.example"], step_ids: [],
    ...guidance, sources: [source],
  }],
  inconclusive_basis_ids: ["basis.uncertain"],
  inconclusive_sections: ["steps"],
  dependencies: [{
    id: "dependency.example", text: "Prerequisite", relation: "blocking_prerequisite",
    status: "blocking", target_procedure_id: "procedure.prerequisite",
    target_procedure: "Prerequisite procedure", target_procedure_version_id: null,
    ...guidance, sources: [source],
  }],
  checklist_items: [{
    id: "item.example", text: "Requirement", classification: "official_requirement",
    classification_label: "Official Requirement", quantity: 1, original_quantity: 1,
    copy_quantity: 0, document_type_id: null, scope: "eligibility_basis",
    ...guidance, sources: [source],
  }],
  steps: [{ id: "step.example", text: "Action", phase: "before", ...guidance, sources: [source] }],
  fees: [{
    id: "fee.example", text: "Fee", value_state: "unknown", amount: null,
    minimum_amount: null, maximum_amount: null, currency: "EGP", fee_type: "administrative",
    current_value_unknown: true, ...guidance, sources: [source],
  }],
  warnings: [{
    id: "warning.example", text: "Regenerate before acting", severity: "important",
    kind: "product", role: "regeneration", ...guidance, sources: [],
  }],
  routing: {
    status: "partially_resolved",
    destinations: [{
      service_point_id: "point.example", service_point_version_id: "point.example.v1",
      association_id: "association.example", name: "Office", address: "Address",
      availability: "unknown", effective_from: "2026-01-01", effective_to: null,
      sources: [source],
    }],
    verification_sources: [source],
  },
};
export const invalid = {
  type: "invalid", diagnostics: [{ code: "invalid_fact_value", path: ["facts", "private_key"] }],
} satisfies PlanningResult;
export const results: PlanningResult[] = [
  {
    type: "next_question", service_id: "service.example",
    question: {
      id: "question.example", text: "Question?",
      answers: [
        { key: "choice", kind: "enum", enum_options: ["a", "b"], minimum: null },
        { key: "age", kind: "integer", enum_options: [], minimum: 0 },
        { key: "confirmed", kind: "boolean", enum_options: [], minimum: null },
        { key: "issued_on", kind: "date", enum_options: [], minimum: null },
        { key: "text", kind: "string", enum_options: [], minimum: null },
      ],
    },
  },
  plan,
  { type: "inconclusive", reason: "unknown_service", message: "Unknown service." },
  invalid,
];

export function jsonResponse(data: unknown, status = 200, headers: HeadersInit = {}): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}
