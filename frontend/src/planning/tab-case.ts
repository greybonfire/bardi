import type { ApiErrorKind } from "@/api/client";
import { freshCase, localToday } from "./state";
import type { ActiveCase } from "./state";
import { createCaseStorage } from "./storage";
import type { StorageNotice } from "./storage";

// Only source data and ephemeral recovery markers survive route remounts. Never
// retain a plan, response, localized Question, or unsubmitted field draft here.
type TabCase = {
  active: ActiveCase;
  notice: StorageNotice;
  storage: ReturnType<typeof createCaseStorage>;
  idle: boolean;
  failure: ApiErrorKind | null;
  retryUntil: number;
};
export type CaseAttachment = {
  state: TabCase;
  isCurrent: () => boolean;
  release: () => void;
};

function requireBrowser() {
  if (typeof window === "undefined" || !window.document) {
    throw new Error("The questionnaire case is browser-only.");
  }
}

// A factory also lets component tests model distinct browser/document lifetimes
// explicitly. Unmounting a route is NOT the end of a browser lifetime.
export function createTabCaseOwner() {
  requireBrowser();
  let current: TabCase | null = null;
  let owner: { cancel: () => void } | null = null;
  let ignoreStoredCase = false;
  let idleOnNextAttach = false;
  let clearNotice: StorageNotice = null;

  const attach = (serviceId: string, cancel: () => void): CaseAttachment => {
    requireBrowser();
    owner?.cancel();
    if (!current || current.active.serviceId !== serviceId) {
      const storage = createCaseStorage(() => window.sessionStorage);
      // A failed deletion must not revive old stored answers later in this
      // document, even when a different Service is opened after clearing.
      const loaded = ignoreStoredCase
        ? { active: freshCase(serviceId), notice: clearNotice }
        : storage.load(serviceId, localToday());
      current = { ...loaded, storage, idle: idleOnNextAttach, failure: null, retryUntil: 0 };
      if (!current.idle && !storage.save(current.active)) current.notice = "memory";
    }
    idleOnNextAttach = false;
    const token = { cancel };
    owner = token;
    return {
      state: current,
      isCurrent: () => owner === token,
      release: () => {
        // An old route's cleanup can cancel only its own local request, never
        // the controller or ownership acquired by a newer route.
        cancel();
        if (owner === token) owner = null;
      },
    };
  };

  return Object.assign(attach, {
    clear(): boolean {
      requireBrowser();
      const previous = owner;
      owner = null; // Invalidate ignored AbortSignals before cancelling work.
      ignoreStoredCase = true;
      idleOnNextAttach = true;
      if (current) {
        current.active = freshCase(current.active.serviceId);
        current.idle = true;
        // Preserve any rate-limit deadline; clearing is not a retry bypass.
      }
      previous?.cancel();
      const cleared = createCaseStorage(() => window.sessionStorage).clear();
      clearNotice = cleared ? null : "clear_failed";
      if (current) current.notice = clearNotice;
      return cleared;
    },
  });
}

// Next's locale root-segment navigation remounts React without reloading the
// document. Initialize this singleton only after mount, with a runtime guard:
// even accidental server use cannot allocate a global case or read Facts.
let browserOwner: ReturnType<typeof createTabCaseOwner> | undefined;
export function attachTabCase(serviceId: string, cancel: () => void): CaseAttachment {
  requireBrowser();
  browserOwner ??= createTabCaseOwner();
  return browserOwner(serviceId, cancel);
}

// Privacy-page escape hatch. No Service lookup, saved-case decoding, or request.
export function clearTabCase(): boolean {
  requireBrowser();
  browserOwner ??= createTabCaseOwner();
  return browserOwner.clear();
}
