import { z } from "zod";
import type { Facts } from "@/api/contract";
import { CASE_VERSION, MAX_FACTS, MAX_KEY_LENGTH, codePoints, freshCase, isCalendarDate, isFacts } from "./state";
import type { ActiveCase } from "./state";

export const CASE_STORAGE_KEY = "bardi.active-case.v1";
const keySchema = z.string().refine((value) => codePoints(value) <= MAX_KEY_LENGTH);
const caseSchema = z.strictObject({
  version: z.literal(CASE_VERSION),
  serviceId: keySchema.refine((value) => /\S/u.test(value)),
  date: z.string().refine(isCalendarDate),
  facts: z.custom<Facts>(isFacts),
  history: z.array(z.strictObject({
    questionId: z.string().min(1).max(2048),
    keys: z.array(keySchema).min(1).max(MAX_FACTS).refine((keys) => new Set(keys).size === keys.length),
  })).max(MAX_FACTS),
});

type TabStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
export type StorageNotice = "restored" | "discarded" | "memory" | "clear_failed" | null;

export function decodeCase(raw: string, serviceId: string): ActiveCase | null {
  // Bound work even if another script/user has filled the tab storage manually.
  if (raw.length > 4 * 1024 * 1024) return null;
  try {
    const result = caseSchema.safeParse(JSON.parse(raw));
    if (!result.success || result.data.serviceId !== serviceId) return null;
    return { ...result.data, facts: Object.fromEntries(Object.entries(result.data.facts)) };
  } catch {
    return null;
  }
}

// Access sessionStorage only after mount. Errors never carry data to logs, and
// a failed write attempts to remove the old case rather than restore stale facts.
export function createCaseStorage(access: () => TabStorage) {
  return {
    load(serviceId: string, today: string): { active: ActiveCase; notice: StorageNotice } {
      const empty = freshCase(serviceId, today);
      try {
        const storage = access();
        const raw = storage.getItem(CASE_STORAGE_KEY);
        if (raw === null) return { active: empty, notice: null };
        const active = decodeCase(raw, serviceId);
        if (active) return { active, notice: "restored" };
        storage.removeItem(CASE_STORAGE_KEY);
        return { active: empty, notice: "discarded" };
      } catch {
        return { active: empty, notice: "memory" };
      }
    },
    save(active: ActiveCase): boolean {
      try {
        // Explicit allow-list: even a wider object at runtime cannot save a plan.
        access().setItem(CASE_STORAGE_KEY, JSON.stringify({
          version: CASE_VERSION, serviceId: active.serviceId, date: active.date,
          facts: active.facts, history: active.history.map(({ questionId, keys }) => ({ questionId, keys })),
        }));
        return true;
      } catch {
        try { access().removeItem(CASE_STORAGE_KEY); } catch { /* Memory-only fallback; caller shows a notice. */ }
        return false;
      }
    },
    clear(): boolean {
      try {
        access().removeItem(CASE_STORAGE_KEY);
        return true;
      } catch {
        return false;
      }
    },
  };
}
