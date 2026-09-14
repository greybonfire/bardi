import "server-only";
import type { InvalidResult } from "./contract";
import { discardBody } from "./http";
import { BodyTooLarge, readPlanningBody, requestDeadline } from "./request.server";
import { configuredSiteOrigin } from "./site-origin.server";
import { fetchPlanning, fetchServices, type UpstreamReply } from "./upstream.server";

function json(data: unknown, status: number, retryAfter: number | null = null): Response {
  const headers: Record<string, string> = {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  };
  if (retryAfter !== null) headers["Retry-After"] = String(retryAfter);
  return new Response(JSON.stringify(data), { status, headers });
}

function invalid(status: number, code: string, path: string[] = [], retryAfter: number | null = null): Response {
  const data: InvalidResult = { type: "invalid", diagnostics: [{ code, path }] };
  return json(data, status, retryAfter);
}

function publicReply<T>(reply: UpstreamReply<T>): Response {
  switch (reply.status) {
    case 200:
    case 400:
    case 413:
    case 422:
      return json(reply.data, reply.status);
    case 429:
      return invalid(429, "rate_limited", [], reply.retryAfter);
    case 503:
      return invalid(503, "unavailable", [], reply.retryAfter);
    case 502:
      return invalid(502, "unexpected_response");
  }
}

export async function proxyServices(request: Request): Promise<Response> {
  const deadline = requestDeadline(request.signal);
  try {
    return publicReply(await fetchServices(deadline.signal));
  } catch {
    return invalid(503, "unavailable");
  } finally {
    deadline.dispose();
  }
}

export async function proxyPlanning(request: Request): Promise<Response> {
  const deadline = requestDeadline(request.signal);
  try {
    const publicOrigin = configuredSiteOrigin();
    if (publicOrigin === null) return invalid(503, "unavailable");

    // The adapter URL may use a private listener origin. Neither that URL nor
    // Host/forwarded headers establish trust; compare browser Origin literally.
    // Missing Origin remains valid for this public, stateless, credential-free
    // API, but an explicit cross-site browser request is always rejected.
    const origin = request.headers.get("origin");
    if ((origin !== null && origin !== publicOrigin)
      || request.headers.get("sec-fetch-site") === "cross-site") {
      return invalid(403, "forbidden_origin");
    }

    let body: Uint8Array<ArrayBuffer>;
    try {
      body = await readPlanningBody(request, deadline.signal);
    } catch (error) {
      if (error instanceof BodyTooLarge) return invalid(413, "body_too_large", ["body"]);
      if (deadline.signal.aborted) return invalid(503, "unavailable");
      return invalid(400, "invalid_body", ["body"]);
    }
    return publicReply(await fetchPlanning(body, deadline.signal));
  } catch {
    return invalid(503, "unavailable");
  } finally {
    deadline.dispose();
    discardBody(request.body);
  }
}
