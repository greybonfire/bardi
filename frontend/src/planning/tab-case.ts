import type { ApiErrorKind } from "@/api/client";
import { localToday } from "./state";
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

  return (serviceId: string, cancel: () => void): CaseAttachment => {
    requireBrowser();
    owner?.cancel();
    if (!current || current.active.serviceId !== serviceId) {
      const storage = createCaseStorage(() => window.sessionStorage);
      const loaded = storage.load(serviceId, localToday());
      current = { ...loaded, storage, idle: false, failure: null, retryUntil: 0 };
      if (!storage.save(current.active)) current.notice = "memory";
    }
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
