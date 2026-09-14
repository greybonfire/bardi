import { fireEvent, render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import Privacy from "@/app/[locale]/privacy/page";
import PlanPage from "@/app/[locale]/services/[serviceId]/plan/page";
import { ClearTabCase } from "./clear-tab-case";
import { attachTabCase, clearTabCase } from "./tab-case";
import { CASE_STORAGE_KEY } from "./storage";

const { directory, refresh } = vi.hoisted(() => ({ directory: vi.fn(), refresh: vi.fn() }));
vi.mock("@/lib/service-pages", () => ({ servicesForPage: directory }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
  notFound: () => { throw new Error("TEST-ONLY not found"); },
}));
const fetchMock = vi.fn();
beforeEach(() => {
  clearTabCase();
  sessionStorage.clear();
  fetchMock.mockReset();
  directory.mockReset();
  refresh.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  expect(fetchMock).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

function saved() {
  const attachment = attachTabCase("test.saved", vi.fn());
  attachment.state.active = {
    ...attachment.state.active,
    facts: { test_answer: false },
    history: [{ questionId: "test.q", keys: ["test_answer"] }],
  };
  attachment.state.idle = false;
  attachment.state.storage.save(attachment.state.active);
  return attachment;
}

it("renders the escape hatch without reading browser state during SSR", () => {
  const storage = vi.spyOn(window, "sessionStorage", "get");
  expect(renderToString(<ClearTabCase locale="en" />)).toContain("Clear this tab");
  expect(storage).not.toHaveBeenCalled();
});

describe.each(["ar", "en"] as const)("privacy clearing (%s)", (locale) => {
  const labels = locale === "ar" ? {
    clear: "امسح الإجابات وابدأ من جديد", confirm: "أيوه، امسح الإجابات", cancel: "خلّي إجاباتي", done: "مسحنا الحالة",
  } : {
    clear: "Clear answers and start again", confirm: "Yes, clear answers", cancel: "Keep my answers", done: "Your case is cleared",
  };
  it("requires confirmation, clears memory and storage, and focuses the outcome without a request", async () => {
    const old = saved();
    const raw = sessionStorage.getItem(CASE_STORAGE_KEY);
    render(await Privacy({ params: Promise.resolve({ locale }) }));
    expect(directory).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: labels.clear }));
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBe(raw);
    fireEvent.click(screen.getByRole("button", { name: labels.cancel }));
    expect(old.state.active.facts).toEqual({ test_answer: false });
    fireEvent.click(screen.getByRole("button", { name: labels.clear }));
    fireEvent.click(screen.getByRole("button", { name: labels.confirm }));
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    expect(old.state.active.facts).toEqual({});
    expect(old.isCurrent()).toBe(false);
    expect(screen.getByRole("status")).toHaveTextContent(labels.done);
    expect(screen.getByRole("status")).toHaveFocus();
  });
});

it.each(["unavailable", "inactive"])("the privacy page can clear when the questionnaire is inaccessible: %s", async (failure) => {
  const old = saved();
  directory.mockResolvedValue(failure === "unavailable" ? { ok: false, kind: "unavailable" } : { ok: true, services: [] });
  const page = PlanPage({ params: Promise.resolve({ locale: "en", serviceId: "test.saved" }) });
  if (failure === "inactive") await expect(page).rejects.toThrow("TEST-ONLY not found");
  else expect(await page).toBeTruthy();
  directory.mockClear();
  render(await Privacy({ params: Promise.resolve({ locale: "en" }) }));
  fireEvent.click(screen.getByRole("button", { name: "Clear answers and start again" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, clear answers" }));
  expect(directory).not.toHaveBeenCalled();
  expect(old.state.active.facts).toEqual({});
  expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
});

it("warns about failed storage deletion rather than claiming the saved copy was removed", () => {
  const old = saved();
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new DOMException("TEST-ONLY", "SecurityError"); });
  render(<ClearTabCase locale="en" />);
  fireEvent.click(screen.getByRole("button", { name: "Clear answers and start again" }));
  fireEvent.click(screen.getByRole("button", { name: "Yes, clear answers" }));
  expect(old.state.active.facts).toEqual({});
  expect(screen.getByRole("status")).toHaveTextContent("browser storage could not be cleared");
  expect(screen.getByRole("status")).toHaveTextContent("Clear this site’s browser data");
  expect(sessionStorage.getItem(CASE_STORAGE_KEY)).not.toBeNull();
});
