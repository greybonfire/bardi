import "server-only";
import { abortable, cancellation } from "./http";

export const MAX_PLANNING_BODY_BYTES = 524_288;
export const API_TIMEOUT_MS = 10_000;

export function requestDeadline(parent?: AbortSignal) {
  const controller = new AbortController();
  const abort = () => controller.abort();
  const timer = setTimeout(abort, API_TIMEOUT_MS);
  parent?.addEventListener("abort", abort, { once: true });
  if (parent?.aborted) abort();
  return {
    signal: controller.signal,
    dispose() {
      clearTimeout(timer);
      parent?.removeEventListener("abort", abort);
    },
  };
}

export class BodyTooLarge extends Error {
  constructor() {
    super("Request body exceeds the byte limit.");
  }
}

export async function readPlanningBody(request: Request, signal: AbortSignal): Promise<Uint8Array<ArrayBuffer>> {
  const declared = request.headers.get("content-length");
  if (declared !== null && /^\d+$/.test(declared) && Number(declared) > MAX_PLANNING_BODY_BYTES) {
    throw new BodyTooLarge();
  }
  if (signal.aborted) throw cancellation();
  if (!request.body) return new Uint8Array(0);

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await abortable(reader.read(), signal);
      if (done) break;
      length += value.byteLength;
      if (length > MAX_PLANNING_BODY_BYTES) throw new BodyTooLarge();
      if (value.byteLength > 0) chunks.push(value);
    }
    const body = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) {
      body.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return body;
  } finally {
    // Do not await a potentially hostile/stalled underlying cancellation hook.
    void reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
