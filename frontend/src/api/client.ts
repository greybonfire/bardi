import { invalidSchema, planningResultSchema, type PlanningRequest, type PlanningResult } from "./contract";
import { abortable, cancellation, discardBody, isAbortError, isJsonResponse, retryAfterSeconds } from "./http";

// Longer than the proxy's 10-second budget, including browser transport and body reads.
export const PLANNING_REQUEST_TIMEOUT_MS = 20_000;
export type ApiErrorKind = "network" | "unavailable" | "rate_limited" | "unexpected_response";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly retryAfter: number | null;

  constructor(kind: ApiErrorKind, retryAfter: number | null = null) {
    super("Planning request could not be completed.");
    this.name = "ApiError";
    this.kind = kind;
    this.retryAfter = retryAfter;
  }
}

export async function requestPlan(input: PlanningRequest, signal: AbortSignal): Promise<PlanningResult> {
  if (signal.aborted) throw cancellation();

  let body: string;
  try {
    // Facts stay in the POST body. Django, not the web client, diagnoses invalid
    // input; do not duplicate domain validation or silently coerce Fact values.
    body = JSON.stringify({
      service_id: input.service_id,
      facts: input.facts,
      locale: input.locale,
      evaluation_context: { evaluation_date: input.evaluation_context.evaluation_date },
    });
  } catch {
    throw new ApiError("unexpected_response");
  }

  // Keep deadline cancellation private: aborting the caller would make the
  // questionnaire ignore this recoverable failure as an intentional navigation.
  const controller = new AbortController();
  const cancel = () => controller.abort();
  let timedOut = false;
  signal.addEventListener("abort", cancel, { once: true });
  if (signal.aborted) cancel();
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, PLANNING_REQUEST_TIMEOUT_MS);

  let response: Response | undefined;
  try {
    if (controller.signal.aborted) throw cancellation();
    response = await abortable(fetch("/v1/planning", {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body,
      signal: controller.signal,
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
      redirect: "error",
    }), controller.signal);

    if (response.status === 429) {
      throw new ApiError("rate_limited", retryAfterSeconds(response.headers.get("retry-after")));
    }
    if (response.status >= 500 && response.status <= 599) {
      throw new ApiError("unavailable", retryAfterSeconds(response.headers.get("retry-after")));
    }
    const invalidStatus = [400, 413, 422].includes(response.status);
    if ((response.status !== 200 && !invalidStatus) || !isJsonResponse(response)) {
      throw new ApiError("unexpected_response");
    }

    let data: unknown;
    try {
      data = await abortable(response.json(), controller.signal);
    } catch (error) {
      if (error instanceof SyntaxError) throw new ApiError("unexpected_response");
      throw error;
    }
    const parsed = (invalidStatus ? invalidSchema : planningResultSchema).safeParse(data);
    if (!parsed.success) throw new ApiError("unexpected_response");
    return parsed.data;
  } catch (error) {
    // Intentional cancellation stays silent. Deadline expiry uses the existing
    // bilingual connection-failure/manual-retry UI; it never retries a POST.
    if (signal.aborted) throw cancellation();
    if (timedOut) throw new ApiError("network");
    if (isAbortError(error)) throw cancellation();
    if (error instanceof ApiError) throw error;
    throw new ApiError("network");
  } finally {
    clearTimeout(timer);
    signal.removeEventListener("abort", cancel);
    if (response) discardBody(response.body);
  }
}
