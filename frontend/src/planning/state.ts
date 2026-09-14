import { calendarDateSchema } from "@/api/contract";
import type { AnswerDefinition, Facts, PlanningResult, Question } from "@/api/contract";

export const CASE_VERSION = 1;
export const MAX_FACTS = 128;
export const MAX_KEY_LENGTH = 128;
export const MAX_STRING_LENGTH = 2048;

// Only source keys and their answer order are retained. Never store a response,
// authored question text (which is locale-specific), a plan, or prepared Facts.
export type AnswerHistory = { questionId: string; keys: string[] };
export type ActiveCase = {
  version: typeof CASE_VERSION;
  serviceId: string;
  date: string;
  facts: Facts;
  history: AnswerHistory[];
};
export type Draft = Record<string, string | boolean>;
export type FieldError = "boolean" | "enum" | "integer" | "minimum" | "date" | "string";
export type AnswerErrors = { fields: Record<string, FieldError>; form?: "required" | "unchanged" | "limits" };

type Invalid = Extract<PlanningResult, { type: "invalid" }>;

export function codePoints(value: string): number {
  return Array.from(value).length;
}

export function isCalendarDate(value: string): boolean {
  return calendarDateSchema.safeParse(value).success;
}

// Calendar dates are local Gregorian dates, not UTC instants.
export function localToday(now = new Date()): string {
  return `${String(now.getFullYear()).padStart(4, "0")}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function freshCase(serviceId: string, date = localToday()): ActiveCase {
  return { version: CASE_VERSION, serviceId, date, facts: {}, history: [] };
}

export function isFacts(value: unknown): value is Facts {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const entries = Object.entries(value);
  return entries.length <= MAX_FACTS && entries.every(([key, fact]) =>
    codePoints(key) <= MAX_KEY_LENGTH && (
      typeof fact === "boolean" ||
      (typeof fact === "number" && Number.isSafeInteger(fact)) ||
      (typeof fact === "string" && codePoints(fact) <= MAX_STRING_LENGTH)
    ),
  );
}

export function questionProblem(question: Question, facts: Facts): boolean {
  const { answers } = question;
  return answers.length === 0 || answers.length > MAX_FACTS ||
    new Set(answers.map(({ key }) => key)).size !== answers.length ||
    answers.some((answer) => codePoints(answer.key) > MAX_KEY_LENGTH ||
      (answer.kind === "enum" && (answer.enum_options.length === 0 ||
        new Set(answer.enum_options).size !== answer.enum_options.length ||
        answer.enum_options.some((value) => codePoints(value) > MAX_STRING_LENGTH))) ||
      (answer.kind === "integer" && answer.minimum !== null && !Number.isSafeInteger(answer.minimum))) ||
    answers.every(({ key }) => Object.hasOwn(facts, key));
}

export function prefill(question: Question, facts: Facts): Draft {
  return Object.fromEntries(question.answers.filter(({ key }) => Object.hasOwn(facts, key))
    .map(({ key }) => [key, typeof facts[key] === "number" ? String(facts[key]) : facts[key]]));
}

function parseField(answer: AnswerDefinition, raw: string | boolean): { value: Facts[string] } | { error: FieldError } {
  switch (answer.kind) {
    case "boolean":
      return typeof raw === "boolean" ? { value: raw } : { error: "boolean" };
    case "enum":
      return typeof raw === "string" && answer.enum_options.includes(raw) ? { value: raw } : { error: "enum" };
    case "integer": {
      // Explicit parsing of an integer form control, never Number("")/truthiness,
      // decimal rounding, exponent notation, whitespace or locale coercion.
      if (typeof raw !== "string" || !/^-?\d+$/.test(raw) || !Number.isSafeInteger(Number(raw))) return { error: "integer" };
      const value = Number(raw);
      return answer.minimum !== null && value < answer.minimum ? { error: "minimum" } : { value };
    }
    case "date":
      return typeof raw === "string" && isCalendarDate(raw) ? { value: raw } : { error: "date" };
    case "string":
      return typeof raw === "string" && codePoints(raw) <= MAX_STRING_LENGTH ? { value: raw } : { error: "string" };
  }
}

export function rewindCase(active: ActiveCase, index: number): ActiveCase {
  if (index < 0 || index >= active.history.length) return active;
  const removed = new Set(active.history.slice(index).flatMap(({ keys }) => keys));
  return {
    ...active,
    facts: Object.fromEntries(Object.entries(active.facts).filter(([key]) => !removed.has(key))),
    history: active.history.slice(0, index),
  };
}

export function submitAnswers(active: ActiveCase, question: Question, draft: Draft):
  { active: ActiveCase } | { errors: AnswerErrors } {
  const errors: Record<string, FieldError> = Object.create(null);
  const values: Facts = Object.create(null);
  for (const answer of question.answers) {
    if (!Object.hasOwn(draft, answer.key)) continue;
    const parsed = parseField(answer, draft[answer.key]);
    if ("error" in parsed) errors[answer.key] = parsed.error;
    else values[answer.key] = parsed.value;
  }
  if (Object.keys(errors).length) return { errors: { fields: errors } };
  if (!Object.keys(values).length) return { errors: { fields: {}, form: "required" } };

  // Editing or omitting a prefilled answer in a recurring multi-Fact question is
  // an earlier-answer correction too: its downstream branch must be discarded.
  const changed = new Set(question.answers.filter(({ key }) => Object.hasOwn(active.facts, key) &&
    (!Object.hasOwn(values, key) || values[key] !== active.facts[key])).map(({ key }) => key));
  const earliest = active.history.findIndex(({ keys }) => keys.some((key) => changed.has(key)));
  const base = earliest < 0 ? active : rewindCase(active, earliest);
  const questionKeys = new Set(question.answers.map(({ key }) => key));
  const facts = Object.fromEntries([
    ...Object.entries(base.facts).filter(([key]) => !questionKeys.has(key)),
    ...Object.entries(values),
  ]);
  if (!isFacts(facts) || base.history.length >= MAX_FACTS) return { errors: { fields: {}, form: "limits" } };
  if (Object.keys(facts).length === Object.keys(active.facts).length &&
    Object.entries(facts).every(([key, value]) => Object.hasOwn(active.facts, key) && active.facts[key] === value)) {
    return { errors: { fields: {}, form: "unchanged" } };
  }
  return { active: { ...base, facts, history: [...base.history, { questionId: question.id, keys: [...questionKeys] }] } };
}

export function diagnosticKeys(result: Invalid): string[] {
  return [...new Set(result.diagnostics.flatMap(({ path }) => {
    const index = path.indexOf("facts");
    const key = index < 0 ? undefined : path[index + 1];
    return typeof key === "string" && codePoints(key) <= MAX_KEY_LENGTH ? [key] : [];
  }))];
}

export function diagnosticDate(result: Invalid): boolean {
  return result.diagnostics.some(({ path }) => path.includes("evaluation_date"));
}

export function correctDiagnostics(active: ActiveCase, keys: string[]): ActiveCase {
  const targeted = new Set(keys);
  const earliest = active.history.findIndex((entry) => entry.keys.some((key) => targeted.has(key)));
  const base = earliest < 0 ? active : rewindCase(active, earliest);
  return { ...base, facts: Object.fromEntries(Object.entries(base.facts).filter(([key]) => !targeted.has(key))) };
}
