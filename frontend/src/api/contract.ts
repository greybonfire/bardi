import { z } from "zod";
import type { components } from "./generated";

type Api = components["schemas"];

export type Locale = Api["PlanningRequest"]["locale"];
export type Service = Api["ServiceNavigationItem"];
export type AnswerDefinition = Api["AnswerDefinitionResponse"];
export type Question = Api["QuestionResponse"];
export type Source = Api["GuidanceSourceResponse"];
export type Freshness = Api["FreshnessResponse"];
export type Plan = Api["PlanResponse"];
export type PlanningResult = Api["PlanningResponse"];
export type InvalidResult = Api["InvalidResponse"];
export type Facts = Record<string, boolean | number | string>;
// The web form omits unanswered Facts. The wire contract also accepts null, which
// Django diagnoses as invalid_fact_value; it is not an unanswered form value.
export type PlanningRequest = Omit<Api["PlanningRequest"], "facts"> & { facts: Facts };

export const localeSchema = z.enum(["ar", "en"]);
export const serviceSchema = z.strictObject({
  id: z.string(),
  title: z.strictObject({ ar: z.string(), en: z.string() }),
});
export const servicesSchema = z.strictObject({ services: z.array(serviceSchema) });

export const answerDefinitionSchema = z.strictObject({
  key: z.string(),
  kind: z.enum(["enum", "integer", "boolean", "date", "string"]),
  enum_options: z.array(z.string()),
  minimum: z.number().int().nullable(),
});
export const questionSchema = z.strictObject({
  id: z.string(),
  text: z.string(),
  answers: z.array(answerDefinitionSchema),
});
export const nextQuestionSchema = z.strictObject({
  type: z.literal("next_question"),
  service_id: z.string(),
  question: questionSchema,
});

export const calendarDateSchema = z.iso.date().refine((value) => !value.startsWith("0000-"));
export const freshnessSchema = z.strictObject({
  state: z.enum(["current", "needs_reverification", "stale", "disputed", "unknown"]),
  verified_on: calendarDateSchema.nullable(),
  reverify_on: calendarDateSchema.nullable(),
});
export const sourceSchema = z.strictObject({
  id: z.string(),
  authority_id: z.string(),
  title: z.string(),
  locator: z.string(),
  classification: z.enum(["official", "field_report", "secondary"]),
  retrieved_on: calendarDateSchema,
});
export const eligibilityBasisSchema = z.strictObject({
  id: z.string(),
  text: z.string(),
  checklist_item_ids: z.array(z.string()),
  step_ids: z.array(z.string()),
  sources: z.array(sourceSchema),
  freshness: freshnessSchema,
});
export const dependencySchema = z.strictObject({
  id: z.string(),
  text: z.string(),
  relation: z.literal("blocking_prerequisite"),
  status: z.enum(["satisfied", "blocking", "unsupported_target", "inconclusive"]),
  target_procedure_id: z.string(),
  target_procedure: z.string(),
  target_procedure_version_id: z.string().nullable(),
  sources: z.array(sourceSchema),
  freshness: freshnessSchema,
});
export const checklistItemSchema = z.strictObject({
  id: z.string(),
  text: z.string(),
  classification: z.enum(["official_requirement", "practical_preparation"]),
  classification_label: z.string(),
  quantity: z.number().int(),
  original_quantity: z.number().int(),
  copy_quantity: z.number().int(),
  document_type_id: z.string().nullable(),
  scope: z.enum(["procedure", "eligibility_basis"]),
  sources: z.array(sourceSchema),
  freshness: freshnessSchema,
});
export const stepSchema = z.strictObject({
  id: z.string(),
  text: z.string(),
  phase: z.string(),
  sources: z.array(sourceSchema),
  freshness: freshnessSchema,
});
export const feeSchema = z.strictObject({
  id: z.string(),
  text: z.string(),
  value_state: z.enum(["known", "range", "unknown", "unverified"]),
  amount: z.number().int().nullable(),
  minimum_amount: z.number().int().nullable(),
  maximum_amount: z.number().int().nullable(),
  currency: z.string(),
  fee_type: z.string(),
  current_value_unknown: z.boolean(),
  sources: z.array(sourceSchema),
  freshness: freshnessSchema,
});
export const warningSchema = z.strictObject({
  id: z.string(),
  text: z.string(),
  severity: z.enum(["info", "important"]),
  kind: z.enum(["administrative", "product"]),
  role: z.enum(["general", "regeneration", "limitation"]),
  sources: z.array(sourceSchema),
  freshness: freshnessSchema,
});
export const servicePointSchema = z.strictObject({
  service_point_id: z.string(),
  service_point_version_id: z.string(),
  association_id: z.string(),
  name: z.string(),
  address: z.string(),
  availability: z.enum(["available", "unknown"]),
  effective_from: calendarDateSchema.nullable(),
  effective_to: calendarDateSchema.nullable(),
  sources: z.array(sourceSchema),
});
export const routingSchema = z.strictObject({
  status: z.enum(["resolved", "partially_resolved", "unresolved"]),
  destinations: z.array(servicePointSchema),
  verification_sources: z.array(sourceSchema),
});
export const planSchema = z.strictObject({
  type: z.literal("plan"),
  service_id: z.string(),
  procedure_id: z.string(),
  procedure_version_id: z.string(),
  title: z.string(),
  eligibility_bases: z.array(eligibilityBasisSchema),
  inconclusive_basis_ids: z.array(z.string()),
  inconclusive_sections: z.array(z.enum(["checklist_items", "steps"])),
  dependencies: z.array(dependencySchema),
  checklist_items: z.array(checklistItemSchema),
  steps: z.array(stepSchema),
  fees: z.array(feeSchema),
  warnings: z.array(warningSchema),
  routing: routingSchema,
});
export const inconclusiveSchema = z.strictObject({
  type: z.literal("inconclusive"),
  reason: z.string(),
  message: z.string(),
});
export const diagnosticSchema = z.strictObject({
  code: z.string(),
  path: z.array(z.union([z.string(), z.number().int()])),
});
export const invalidSchema = z.strictObject({
  type: z.literal("invalid"),
  diagnostics: z.array(diagnosticSchema),
});
export const planningResultSchema = z.discriminatedUnion("type", [
  nextQuestionSchema,
  planSchema,
  inconclusiveSchema,
  invalidSchema,
]);

// Pydantic counts Unicode code points, not JavaScript UTF-16 code units.
const boundedString = (maximum: number) =>
  z.string().refine((value) => Array.from(value).length <= maximum);
const factValueSchema = z.union([z.boolean(), z.number().int(), boundedString(2048)]);
export const factsSchema = z.record(boundedString(128), factValueSchema)
  .refine((facts) => Object.keys(facts).length <= 128);
export const transportPlanningRequestSchema = z.strictObject({
  service_id: boundedString(128).refine((value) => /\S/u.test(value)),
  facts: z.record(boundedString(128), factValueSchema.nullable())
    .refine((facts) => Object.keys(facts).length <= 128),
  locale: localeSchema,
  evaluation_context: z.strictObject({ evaluation_date: calendarDateSchema }),
});
export const planningRequestSchema = transportPlanningRequestSchema.extend({ facts: factsSchema });

// Check both directions WITHOUT widening the inferred Zod outputs. A newly
// required/optional backend field, or a widened/narrowed enum, must fail tsc.
export const apiSchemas = {
  AnswerDefinitionResponse: answerDefinitionSchema,
  ChecklistItemResponse: checklistItemSchema,
  DiagnosticResponse: diagnosticSchema,
  EligibilityBasisResponse: eligibilityBasisSchema,
  EvaluationContext: transportPlanningRequestSchema.shape.evaluation_context,
  FeeResponse: feeSchema,
  FreshnessResponse: freshnessSchema,
  GuidanceSourceResponse: sourceSchema,
  InconclusiveResponse: inconclusiveSchema,
  InvalidResponse: invalidSchema,
  LocalizedTitleResponse: serviceSchema.shape.title,
  NavigationResponse: servicesSchema,
  NextQuestionResponse: nextQuestionSchema,
  PlanResponse: planSchema,
  PlanningRequest: transportPlanningRequestSchema,
  PlanningResponse: planningResultSchema,
  ProcedureDependencyResponse: dependencySchema,
  QuestionResponse: questionSchema,
  RoutingResponse: routingSchema,
  ServiceNavigationItem: serviceSchema,
  ServicePointResponse: servicePointSchema,
  StepResponse: stepSchema,
  TransportValue: factValueSchema.nullable(),
  WarningResponse: warningSchema,
};
type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends
  (<T>() => T extends B ? 1 : 2) ? true : false;
type Assert<T extends true> = T;
export type OpenApiContractCheck = Assert<Equal<
  { [K in keyof typeof apiSchemas]: z.output<(typeof apiSchemas)[K]> },
  Api
>>;
export type WebRequestContractCheck = Assert<Equal<
  z.output<typeof planningRequestSchema>,
  { service_id: string; facts: Facts; locale: Locale; evaluation_context: Api["EvaluationContext"] }
>>;
