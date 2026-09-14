import "server-only";
import type { z } from "zod";
import { invalidSchema, planningResultSchema, servicesSchema, type InvalidResult } from "./contract";
import { abortable, discardBody, isJsonResponse, retryAfterSeconds } from "./http";

export type UpstreamReply<T> =
  | { status: 200; data: T }
  | { status: 400 | 413 | 422; data: InvalidResult }
  | { status: 429 | 503; retryAfter: number | null }
  | { status: 502 };

function apiOrigin(): string | null {
  const configured = process.env.BARDI_API_ORIGIN
    ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : undefined);
  if (!configured || configured.trim() !== configured) return null;
  try {
    const url = new URL(configured);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password
      || url.pathname !== "/" || url.search || url.hash) return null;
    return url.origin;
  } catch {
    return null;
  }
}

async function requestUpstream<T>(
  endpoint: "services" | "planning",
  schema: z.ZodType<T>,
  signal: AbortSignal,
  body?: Uint8Array<ArrayBuffer>,
): Promise<UpstreamReply<T>> {
  let response: Response | undefined;
  try {
    const origin = apiOrigin();
    if (!origin || signal.aborted) return { status: 503, retryAfter: null };
    // No user-controlled URL, query, cookies, authorization, referrer, or proxy
    // identity headers. Django sees this proxy's IP unless trusted ingress is
    // configured separately; never synthesize X-Forwarded-For to evade its limits.
    const path = endpoint === "services" ? "/v1/services" : "/v1/planning";
    response = await abortable(fetch(`${origin}${path}`, {
      method: endpoint === "services" ? "GET" : "POST",
      headers: endpoint === "services"
        ? { Accept: "application/json" }
        : { Accept: "application/json", "Content-Type": "application/json" },
      ...(body === undefined ? {} : { body }),
      signal,
      credentials: "omit",
      cache: "no-store",
      referrerPolicy: "no-referrer",
      redirect: "manual",
    }), signal);

    if (response.status === 429) {
      return { status: 429, retryAfter: retryAfterSeconds(response.headers.get("retry-after")) };
    }
    if (response.status >= 500 && response.status <= 599) {
      return { status: 503, retryAfter: retryAfterSeconds(response.headers.get("retry-after")) };
    }
    const invalidStatus = endpoint === "planning" && [400, 413, 422].includes(response.status);
    if ((response.status !== 200 && !invalidStatus) || !isJsonResponse(response)) return { status: 502 };

    let data: unknown;
    try {
      data = await abortable(response.json(), signal);
    } catch (error) {
      if (error instanceof SyntaxError) return { status: 502 };
      return { status: 503, retryAfter: null };
    }
    if (invalidStatus) {
      const parsed = invalidSchema.safeParse(data);
      if (!parsed.success) return { status: 502 };
      return { status: response.status as 400 | 413 | 422, data: parsed.data };
    }
    const parsed = schema.safeParse(data);
    return parsed.success ? { status: 200, data: parsed.data } : { status: 502 };
  } catch {
    // Never let Next's exception reporting receive configuration or request data.
    return { status: 503, retryAfter: null };
  } finally {
    if (response) discardBody(response.body);
  }
}

export function fetchServices(signal: AbortSignal) {
  return requestUpstream("services", servicesSchema, signal);
}

export function fetchPlanning(body: Uint8Array<ArrayBuffer>, signal: AbortSignal) {
  return requestUpstream("planning", planningResultSchema, signal, body);
}
