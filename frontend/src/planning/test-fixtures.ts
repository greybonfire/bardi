import type { AnswerDefinition, Plan, PlanningResult, Question, Service } from "@/api/contract";

export const service: Service = { id: "service.test", title: { ar: "خدمة الاختبار", en: "Test service" } };
export function answer(key: string, kind: AnswerDefinition["kind"], extra: Partial<AnswerDefinition> = {}): AnswerDefinition {
  return { key, kind, enum_options: [], minimum: null, ...extra };
}
export function question(id = "q.father", answers = [answer("father_alive", "boolean")], text = "Is your father alive?"): Question {
  return { id, answers, text };
}
export function next(q = question(), serviceId = service.id): PlanningResult {
  return { type: "next_question", service_id: serviceId, question: q };
}
export function plan(serviceId = service.id): Plan {
  return {
    type: "plan", service_id: serviceId, procedure_id: "procedure.test", procedure_version_id: "version.test",
    title: "Authored preparation plan", eligibility_bases: [], inconclusive_basis_ids: [], inconclusive_sections: [],
    dependencies: [], checklist_items: [], steps: [], fees: [], warnings: [],
    routing: { status: "unresolved", destinations: [], verification_sources: [] },
  };
}
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
