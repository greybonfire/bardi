import "server-only";
import type { Service } from "./contract";
import { requestDeadline } from "./request.server";
import { fetchServices } from "./upstream.server";

export type ServicesResult =
  | { ok: true; services: Service[] }
  | { ok: false; kind: "unavailable" | "rate_limited" };

export async function getServices(): Promise<ServicesResult> {
  const deadline = requestDeadline();
  try {
    const reply = await fetchServices(deadline.signal);
    if (reply.status === 200) return { ok: true, services: reply.data.services };
    return { ok: false, kind: reply.status === 429 ? "rate_limited" : "unavailable" };
  } catch {
    return { ok: false, kind: "unavailable" };
  } finally {
    deadline.dispose();
  }
}
