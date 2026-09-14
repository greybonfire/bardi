// Shared transport mechanics only. Never attach payloads, validation issues,
// upstream errors, URLs, or AbortSignal.reason to an exception.
export function cancellation(): DOMException {
  return new DOMException("Request cancelled.", "AbortError");
}

export function isAbortError(error: unknown): boolean {
  return error instanceof Error && error.name === "AbortError";
}

export function abortable<T>(pending: Promise<T>, signal: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    const abort = () => {
      signal.removeEventListener("abort", abort);
      reject(cancellation());
    };
    signal.addEventListener("abort", abort, { once: true });
    pending.then(
      (value) => {
        signal.removeEventListener("abort", abort);
        if (signal.aborted) reject(cancellation());
        else resolve(value);
      },
      (error: unknown) => {
        signal.removeEventListener("abort", abort);
        reject(signal.aborted ? cancellation() : error);
      },
    );
    if (signal.aborted) abort();
  });
}

// Django sends delta-seconds. Do not propagate arbitrary header strings or dates.
export function retryAfterSeconds(value: string | null): number | null {
  if (value === null || !/^\d{1,5}$/.test(value)) return null;
  const seconds = Number(value);
  return seconds <= 86_400 ? seconds : null;
}

export function isJsonResponse(response: Response): boolean {
  return response.headers.get("content-type")?.split(";", 1)[0].trim().toLowerCase()
    === "application/json";
}

export function discardBody(body: ReadableStream<Uint8Array> | null): void {
  // Cancellation must not delay a response, even if an underlying stream stalls.
  // Locked/already-consumed bodies may reject cancellation; never surface that.
  try {
    void body?.cancel().catch(() => undefined);
  } catch {
    // No error capture or logging at the public boundary.
  }
}
