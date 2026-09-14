import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PlanningResult } from "@/api/contract";
import { ApiError, requestPlan } from "@/api/client";
import { Questionnaire } from "./questionnaire";
import { fieldLabel } from "./labels";
import { CASE_STORAGE_KEY } from "./storage";
import { freshCase, localToday } from "./state";
import * as tabCase from "./tab-case";
import { answer, deferred, next, plan, question, service } from "./test-fixtures";

vi.mock("@/api/client", async (original) => ({ ...await original<typeof import("@/api/client")>(), requestPlan: vi.fn() }));
const request = vi.mocked(requestPlan);
const renderEnglish = () => render(<Questionnaire service={service} locale="en" />);
const continueButton = () => screen.getByRole("button", { name: "Continue" });
const review = () => fireEvent.click(screen.getByText("Review or change answers"));
const expandDate = () => fireEvent.click(screen.getByText(/^Guidance date:/));
const newBrowserLifetime = () => vi.spyOn(tabCase, "attachTabCase").mockImplementation(tabCase.createTabCaseOwner());
const history = (keys: string[], questionId = `q.${keys[0]}`) => ({ questionId, keys });
const putCase = (facts: Record<string, string | boolean | number>, entries: ReturnType<typeof history>[], date = "2020-02-29") => {
  const active = { ...freshCase(service.id, date), facts, history: entries };
  sessionStorage.setItem(CASE_STORAGE_KEY, JSON.stringify(active));
  return active;
};
const stored = () => JSON.parse(sessionStorage.getItem(CASE_STORAGE_KEY)!);
const chooseNo = async () => {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("radio", { name: "No" }));
  await user.click(continueButton());
};

beforeEach(() => {
  // Each test is a new tab/document, while locale route remounts share an owner.
  newBrowserLifetime();
  sessionStorage.clear();
  request.mockReset();
  request.mockResolvedValue(next());
});
afterEach(() => { vi.useRealTimers(); });

describe("hydration, native fields and semantic progression", () => {
  it("does not access browser storage during SSR, then restores after hydration", async () => {
    putCase({ father_alive: false }, [history(["father_alive"])]);
    request.mockResolvedValue(next(question("q.sex", [answer("sex", "enum", { enum_options: ["male", "female"] })], "Authored next question")));
    const get = vi.spyOn(Storage.prototype, "getItem");
    const container = document.createElement("div");
    container.innerHTML = renderToString(<Questionnaire service={service} locale="en" />);
    document.body.append(container);
    expect(get).not.toHaveBeenCalled();
    expect(request).not.toHaveBeenCalled();
    expect(tabCase.attachTabCase).not.toHaveBeenCalled();
    expect(container).toHaveTextContent("The questionnaire needs JavaScript.");
    expect(container).toHaveTextContent("Enable JavaScript and reload this page");
    expect(within(container).getByRole("link", { name: "Back to the service introduction" })).toHaveAttribute("href", `/en/services/${service.id}`);
    render(<Questionnaire service={service} locale="en" />, { container, hydrate: true });
    await screen.findByRole("heading", { name: "Authored next question" });
    expect(screen.queryByText("The questionnaire needs JavaScript.")).not.toBeInTheDocument();
    expect(request.mock.calls[0][0]).toMatchObject({ facts: { father_alive: false }, evaluation_context: { evaluation_date: "2020-02-29" } });
  });
  it.each(["ar", "en"] as const)("keeps %s SSR recovery plain and visible even when a browser case already exists", async (locale) => {
    putCase({ residence_district: "TEST-ONLY-private-answer" }, [history(["residence_district"])]);
    request.mockResolvedValue(plan());
    const mounted = renderEnglish();
    await screen.findByText("Authored preparation plan");
    mounted.unmount();
    const calls = request.mock.calls.length;
    const attachments = vi.mocked(tabCase.attachTabCase).mock.calls.length;
    const html = renderToString(<Questionnaire service={service} locale={locale} />);
    expect(html).toContain(locale === "ar" ? "الأسئلة محتاجة JavaScript." : "The questionnaire needs JavaScript.");
    expect(html).not.toMatch(/<noscript|TEST-ONLY-private-answer|Authored preparation plan/);
    expect(request).toHaveBeenCalledTimes(calls);
    expect(tabCase.attachTabCase).toHaveBeenCalledTimes(attachments);
  });
  it.each(["ar", "en"] as const)("discloses %s privacy and the date form only on expansion, showing the canonical date", async (locale) => {
    const user = userEvent.setup();
    render(<Questionnaire service={service} locale={locale} />);
    await screen.findByRole("heading", { name: "Is your father alive?" });
    const privacy = screen.getByText(locale === "ar" ? "إجاباتك وخصوصيتك" : "Your answers and privacy");
    const date = screen.getByText(locale === "ar" ? /^تاريخ الإرشادات:/ : /^Guidance date:/);
    expect(privacy.closest("details")).not.toHaveAttribute("open");
    expect(date.closest("details")).not.toHaveAttribute("open");
    expect(date).toHaveTextContent(localToday());
    await user.click(privacy);
    expect(privacy.closest("details")).toHaveAttribute("open");
    expect(privacy.closest("details")).toHaveTextContent(locale === "ar" ? "المتصفح ممكن يرجّع التبويبات" : "Browsers may restore tabs.");
    await user.click(date);
    expect(date.closest("details")).toHaveAttribute("open");
    const input = screen.getByLabelText(locale === "ar" ? "تاريخ الإرشادات" : "Guidance date");
    fireEvent.change(input, { target: { value: "2024-02-29" } });
    expect(date).toHaveTextContent(localToday()); // Drafts do not relabel current guidance.
    await user.click(screen.getByRole("button", { name: locale === "ar" ? "استخدم التاريخ ده" : "Use this date" }));
    expect(date).toHaveTextContent("2024-02-29");
    expect(request.mock.calls[1][0].evaluation_context.evaluation_date).toBe("2024-02-29");
  });
  it("defaults to Arabic, sends empty source facts and local today, and preserves authored text", async () => {
    const text = "هل والدك على قيد الحياة؟\nنص مؤلف كما هو.";
    request.mockResolvedValue(next(question("q.ar", undefined, text)));
    const { container } = render(<Questionnaire service={service} />);
    await screen.findByRole("heading", { name: /هل والدك على قيد الحياة/ });
    expect(container.querySelector("h2")?.textContent).toBe(text);
    expect(container.querySelector(".planning")).toHaveAttribute("dir", "rtl");
    expect(request.mock.calls[0][0]).toEqual({ service_id: service.id, facts: {}, locale: "ar", evaluation_context: { evaluation_date: localToday() } });
    expect(screen.getByRole("radio", { name: "أيوه" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "لأ" })).not.toBeChecked();
    expect(container.querySelector("h1")).toBeNull();
    await waitFor(() => expect(container.querySelector(".planning-stage")).toHaveFocus());
  });
  it("requires an explicit boolean, focuses validation, and sends No as false", async () => {
    request.mockResolvedValueOnce(next()).mockResolvedValueOnce(plan());
    renderEnglish();
    await screen.findByRole("radio", { name: "No" });
    fireEvent.click(continueButton());
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(request).toHaveBeenCalledTimes(1);
    await chooseNo();
    await screen.findByText("Authored preparation plan");
    expect(request.mock.calls[1][0].facts).toEqual({ father_alive: false });
    expect(stored().facts).toEqual({ father_alive: false });
    expect(stored()).not.toHaveProperty("plan");
  });
  it.each(["en", "ar"] as const)("renders every multi-Fact field in %s and sends exact typed values", async (locale) => {
    const q = question("q.all", [
      answer("father_alive", "boolean"), answer("other_living_sons_of_father_count", "integer", { minimum: 0 }),
      answer("birth_date", "date"), answer("residence_district", "string"),
      answer("citizenship", "enum", { enum_options: ["egyptian", "future_RAW"] }),
    ], locale === "ar" ? "سؤال مؤلف لعدة معلومات" : "Authored multi-Fact question");
    request.mockResolvedValueOnce(next(q)).mockResolvedValueOnce(plan());
    render(<Questionnaire service={service} locale={locale} />);
    await screen.findByRole("heading", { name: q.text });
    expect(screen.getAllByRole("radio")).toHaveLength(4);
    expect(screen.getAllByRole("radio").every((input) => !(input as HTMLInputElement).checked)).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: locale === "ar" ? "لأ" : "No" }));
    fireEvent.click(screen.getByRole("radio", { name: "future_RAW" }));
    fireEvent.change(screen.getByLabelText(fieldLabel("other_living_sons_of_father_count", locale)), { target: { value: "0" } });
    fireEvent.change(screen.getByLabelText(fieldLabel("birth_date", locale)), { target: { value: "2000-02-29" } });
    const text = `  مصر ${"𓀀".repeat(2040)}`;
    const input = screen.getByLabelText(fieldLabel("residence_district", locale));
    expect(input).not.toHaveAttribute("maxlength");
    fireEvent.change(input, { target: { value: text } });
    fireEvent.click(screen.getByRole("button", { name: locale === "ar" ? "كمّل" : "Continue" }));
    await screen.findByText("Authored preparation plan");
    expect(request.mock.calls[1][0].facts).toEqual({ father_alive: false, other_living_sons_of_father_count: 0, birth_date: "2000-02-29", residence_district: text, citizenship: "future_RAW" });
  });
  it("does not silently coerce integer notation or truncate Unicode strings", async () => {
    const q = question("q.validation", [answer("count", "integer", { minimum: 0 }), answer("text", "string")], "Authored validation question");
    request.mockResolvedValue(next(q));
    renderEnglish();
    await screen.findByRole("heading", { name: q.text });
    fireEvent.change(screen.getByLabelText("count"), { target: { value: "1e2" } });
    fireEvent.change(screen.getByLabelText("text"), { target: { value: "𓀀".repeat(2049) } });
    fireEvent.click(continueButton());
    const alert = screen.getByRole("alert");
    expect(alert).toHaveFocus();
    expect(alert).toHaveTextContent("Do not use decimals or exponent notation");
    expect(alert).toHaveTextContent("no more than 2,048 characters");
    expect(screen.getByLabelText("text")).toHaveValue("𓀀".repeat(2049));
    expect(screen.getByLabelText("count")).toHaveAttribute("aria-invalid", "true");
    fireEvent.click(within(alert).getByRole("link", { name: /^count:/ }));
    expect(screen.getByLabelText("count")).toHaveFocus();
    expect(request).toHaveBeenCalledTimes(1);
  });
  it("handles partially answered recurrence, prefill and no-progress validation", async () => {
    const q = question("q.multi", [answer("father_alive", "boolean"), answer("other_living_sons_of_father_count", "integer", { minimum: 0 })], "Authored family question");
    request.mockResolvedValueOnce(next(q)).mockResolvedValueOnce(next(q)).mockResolvedValueOnce(plan());
    renderEnglish();
    await chooseNo();
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    await screen.findByRole("heading", { name: q.text });
    expect(request.mock.calls[1][0].facts).toEqual({ father_alive: false });
    expect(screen.getByRole("radio", { name: "No" })).toBeChecked();
    expect(screen.getByLabelText("Father’s other living sons")).toHaveValue("");
    fireEvent.click(continueButton());
    expect(screen.getByRole("alert")).toHaveTextContent("Answer a missing field");
    expect(request).toHaveBeenCalledTimes(2);
    fireEvent.change(screen.getByLabelText("Father’s other living sons"), { target: { value: "0" } });
    fireEvent.click(continueButton());
    await screen.findByText("Authored preparation plan");
    expect(request.mock.calls[2][0].facts).toEqual({ father_alive: false, other_living_sons_of_father_count: 0 });
  });
  it("omitting a prefilled field removes it and its downstream branch", async () => {
    const q = question("q.multi", [answer("father_alive", "boolean"), answer("other_living_sons_of_father_count", "integer")], "Authored family question");
    putCase({ father_alive: true, middle: "stale" }, [history(q.answers.map(({ key }) => key), q.id), history(["middle"])]);
    request.mockResolvedValueOnce(next(q)).mockResolvedValueOnce(plan());
    renderEnglish();
    await screen.findByRole("heading", { name: q.text });
    fireEvent.click(screen.getByRole("button", { name: "Leave unanswered: Father is alive" }));
    fireEvent.change(screen.getByLabelText("Father’s other living sons"), { target: { value: "2" } });
    fireEvent.click(continueButton());
    await screen.findByText("Authored preparation plan");
    expect(request.mock.calls[1][0].facts).toEqual({ other_living_sons_of_father_count: 2 });
    expect(stored().history).toEqual([history(q.answers.map(({ key }) => key), q.id)]);
  });
  it("handles fully answered recurring Questions without an automatic loop or trapped form", async () => {
    renderEnglish();
    await chooseNo();
    await screen.findByRole("heading", { name: "We can’t continue with this question" });
    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("button", { name: "Continue" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again with these answers" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Clear answers and start again" })).toBeEnabled();
    review();
    expect(screen.getByRole("button", { name: "Change answer: Father is alive" })).toBeEnabled();
  });
  it.each([
    question("q.empty", []),
    question("q.duplicate", [answer("same", "string"), answer("same", "string")]),
    question("q.long", [answer("x".repeat(129), "boolean")]),
  ])("offers safe recovery for unrenderable answer definitions ($id)", async (q) => {
    request.mockResolvedValue(next(q));
    renderEnglish();
    await screen.findByRole("heading", { name: "We can’t continue with this question" });
    expect(request).toHaveBeenCalledTimes(1);
  });
});

describe("review, diagnostics and refresh recovery", () => {
  it("review/change discards the targeted and subsequent source facts before resubmitting", async () => {
    putCase({ citizenship: "egyptian", father_alive: true, birth_date: "1990-01-01" }, [history(["citizenship"]), history(["father_alive"]), history(["birth_date"])]);
    request.mockResolvedValueOnce(plan()).mockResolvedValueOnce(next());
    renderEnglish();
    await screen.findByText("Authored preparation plan");
    review();
    fireEvent.click(screen.getByRole("button", { name: "Change answer: Father is alive" }));
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request.mock.calls[1][0].facts).toEqual({ citizenship: "egyptian" });
    expect(stored().facts).toEqual({ citizenship: "egyptian" });
    expect(stored().history).toEqual([history(["citizenship"])]);
    await waitFor(() => expect(document.activeElement).toHaveClass("planning-stage"));
  });
  it("invalid diagnostics correct the earliest matching answer, including recurring fields", async () => {
    putCase({ citizenship: "egyptian", father_alive: true, middle: false, sons: 0, unknown: true }, [history(["citizenship"]), history(["father_alive", "sons"], "q.multi"), history(["middle"]), history(["father_alive", "sons"], "q.multi")]);
    request.mockResolvedValueOnce({ type: "invalid", diagnostics: [
      { code: "contradictory_facts", path: ["facts", "middle"] }, { code: "contradictory_facts", path: ["facts", "sons"] }, { code: "invalid_fact_value", path: ["facts", "unknown"] },
    ] }).mockResolvedValueOnce(next());
    renderEnglish();
    await screen.findByRole("heading", { name: "Some information needs checking" });
    expect(screen.getByRole("alert")).toHaveTextContent("Some answers conflict");
    fireEvent.click(screen.getByRole("button", { name: "Correct these answers" }));
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request.mock.calls[1][0].facts).toEqual({ citizenship: "egyptian" });
    expect(stored().history).toEqual([history(["citizenship"])]);
  });
  it("unknown/prototype-shaped diagnostic keys are safely removed without invented prompts", async () => {
    putCase(JSON.parse('{"__proto__":true,"citizenship":"egyptian"}'), [history(["citizenship"])]);
    request.mockResolvedValueOnce({ type: "invalid", diagnostics: [{ code: "unsupported_fact_key", path: ["body", "facts", "__proto__"] }] }).mockResolvedValueOnce(next());
    renderEnglish();
    fireEvent.click(await screen.findByRole("button", { name: "Correct these answers" }));
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request.mock.calls[1][0].facts).toEqual({ citizenship: "egyptian" });
    expect({}).not.toHaveProperty("polluted");
  });
  it("diagnoses the evaluation date with a focused native correction control", async () => {
    request.mockResolvedValue({ type: "invalid", diagnostics: [{ code: "invalid_request", path: ["body", "evaluation_context", "evaluation_date"] }] });
    renderEnglish();
    const correct = await screen.findByRole("button", { name: "Correct the date" });
    const details = screen.getByLabelText("Guidance date").closest("details");
    expect(details).not.toHaveAttribute("open");
    fireEvent.click(correct);
    expect(details).toHaveAttribute("open");
    expect(screen.getByLabelText("Guidance date")).toHaveFocus();
    fireEvent.change(screen.getByLabelText("Guidance date"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Use this date" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a real Gregorian date");
    expect(request).toHaveBeenCalledTimes(1);
  });
  it("gives recovery for untargeted invalid input or invalid knowledge without exposing diagnostics", async () => {
    request.mockResolvedValue({ type: "invalid", diagnostics: [{ code: "knowledge_configuration_invalid", path: [] }] });
    renderEnglish();
    await screen.findByRole("heading", { name: "Some information needs checking" });
    expect(screen.getByRole("button", { name: "Try again with these answers" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Clear answers and start again" })).toBeEnabled();
    expect(document.body).not.toHaveTextContent("knowledge_configuration_invalid");
  });
  it("refresh restores the current failed case and date, never a stale plan", async () => {
    request.mockResolvedValueOnce(next()).mockRejectedValueOnce(new ApiError("network"));
    const mounted = renderEnglish();
    await chooseNo();
    await screen.findByRole("heading", { name: "We couldn’t continue" });
    expect(stored().facts).toEqual({ father_alive: false });
    mounted.unmount();
    newBrowserLifetime(); // A document reload, not a locale route remount.
    request.mockResolvedValueOnce(plan());
    renderEnglish();
    await screen.findByText("Authored preparation plan");
    expect(request.mock.calls[2][0]).toMatchObject({ facts: { father_alive: false }, evaluation_context: { evaluation_date: localToday() } });
    expect(screen.getByText(/Your answers from this tab are back/)).toBeInTheDocument();
    expect(stored()).toEqual({ ...freshCase(service.id), facts: { father_alive: false }, history: [history(["father_alive"], "q.father")] });
  });
  it("discarded corrupt storage starts safely with empty facts", async () => {
    sessionStorage.setItem(CASE_STORAGE_KEY, '{"version":99,"facts":{"secret":true}}');
    renderEnglish();
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request.mock.calls[0][0].facts).toEqual({});
    expect(screen.getByText(/previous tab case could not be used/)).toBeInTheDocument();
  });
});

describe("cancellation, isolation and privacy", () => {
  it("cancels locale remounts and never displays old-locale questions, even in review", async () => {
    const old = deferred<PlanningResult>();
    const translated = deferred<PlanningResult>();
    request.mockResolvedValueOnce(next()).mockReturnValueOnce(old.promise).mockReturnValueOnce(translated.promise);
    const mounted = renderEnglish();
    await chooseNo();
    expect(request).toHaveBeenCalledTimes(2);
    mounted.unmount();
    render(<Questionnaire service={service} locale="ar" />);
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(request.mock.calls[1][1].aborted).toBe(true);
    expect(request.mock.calls[2][0]).toMatchObject({ locale: "ar", facts: { father_alive: false } });
    expect(document.body).not.toHaveTextContent("Is your father alive?");
    expect(document.body).not.toHaveTextContent("Father is alive");
    await act(async () => old.resolve(plan()));
    expect(screen.queryByText("Authored preparation plan")).not.toBeInTheDocument();
    const authored = "ما الجنس المثبت في مستنداتك الرسمية؟";
    await act(async () => translated.resolve(next(question("q.sex", [answer("sex", "enum", { enum_options: ["male", "female"] })], authored))));
    expect(screen.getByRole("heading", { name: authored })).toBeInTheDocument();
    expect(stored()).not.toHaveProperty("locale");
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).not.toContain("Is your father alive?");
  });
  it.each(["result", "failure"] as const)("a newer mount owns its request despite late old cleanup and an ignored-abort %s", async (outcome) => {
    const old = deferred<PlanningResult>();
    const current = deferred<PlanningResult>();
    request.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise);
    const mounted = renderEnglish();
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    const translated = render(<Questionnaire service={service} locale="ar" />);
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    expect(request.mock.calls[0][1].aborted).toBe(true);
    mounted.unmount(); // Must not abort the newer mount's controller.
    expect(request.mock.calls[1][1].aborted).toBe(false);
    await act(async () => {
      if (outcome === "result") old.resolve(plan());
      else old.reject(new ApiError("rate_limited", 3600));
      current.resolve({ type: "inconclusive", reason: "unsupported", message: "رسالة مؤلفة جديدة" });
    });
    expect(within(translated.container).getByText("رسالة مؤلفة جديدة")).toBeInTheDocument();
    expect(screen.queryByText("Authored preparation plan")).not.toBeInTheDocument();
    expect(screen.queryByText(/تقدر تجرّب تاني بعد/)).not.toBeInTheDocument();
    translated.unmount();
    renderEnglish();
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request).toHaveBeenCalledTimes(3);
  });
  it("isolates Services and aborts an old Service’s request, with no case archive", async () => {
    putCase({ father_alive: false }, [history(["father_alive"])]);
    const old = deferred<PlanningResult>();
    const other = { ...service, id: "service.other" };
    request.mockReturnValueOnce(old.promise).mockResolvedValueOnce(next(question(), other.id)).mockResolvedValueOnce(next());
    const mounted = renderEnglish();
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    mounted.rerender(<Questionnaire service={other} locale="en" />);
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request.mock.calls[0][1].aborted).toBe(true);
    expect(request.mock.calls[1][0]).toMatchObject({ service_id: other.id, facts: {} });
    await act(async () => old.resolve(plan()));
    expect(screen.queryByText("Authored preparation plan")).not.toBeInTheDocument();
    mounted.rerender(<Questionnaire service={service} locale="en" />);
    await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
    expect(request.mock.calls[2][0].facts).toEqual({});
    expect(sessionStorage.length).toBe(1);
    expect(stored().serviceId).toBe(service.id);
  });
  it("reset requires inline confirmation, aborts in flight and clears app/storage without an automatic new request", async () => {
    const old = deferred<PlanningResult>();
    request.mockResolvedValueOnce(next()).mockReturnValueOnce(old.promise).mockResolvedValueOnce(next());
    const mounted = renderEnglish();
    await chooseNo();
    const signal = request.mock.calls[1][1];
    fireEvent.click(screen.getByRole("button", { name: "Clear answers and start again" }));
    expect(screen.getByRole("heading", { name: "Clear this case?" }).parentElement).toHaveFocus();
    expect(signal.aborted).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Keep my answers" }));
    expect(stored().facts).toEqual({ father_alive: false });
    fireEvent.click(screen.getByRole("button", { name: "Clear answers and start again" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, clear answers" }));
    expect(signal.aborted).toBe(true);
    expect(screen.getByRole("heading", { name: "Your case is cleared" })).toBeInTheDocument();
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    await act(async () => old.resolve(plan()));
    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("Authored preparation plan")).not.toBeInTheDocument();
    mounted.unmount();
    render(<Questionnaire service={service} locale="ar" />);
    expect(screen.getByRole("heading", { name: "مسحنا الحالة" })).toBeInTheDocument();
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    expect(request).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole("button", { name: "ابدأ من جديد" }));
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request.mock.calls[2][0].facts).toEqual({});
  });
  it("an earlier-answer edit aborts pending results and clears the branch immediately", async () => {
    const old = deferred<PlanningResult>();
    request.mockResolvedValueOnce(next()).mockReturnValueOnce(old.promise).mockResolvedValueOnce(next());
    renderEnglish();
    await chooseNo();
    review();
    fireEvent.click(screen.getByRole("button", { name: "Change answer: Father is alive" }));
    expect(request.mock.calls[1][1].aborted).toBe(true);
    expect(stored().facts).toEqual({});
    await screen.findByRole("heading", { name: "Is your father alive?" });
    await act(async () => old.resolve(plan()));
    expect(screen.getByRole("heading", { name: "Is your father alive?" })).toBeInTheDocument();
    expect(screen.queryByText("Authored preparation plan")).not.toBeInTheDocument();
  });
  it("date draft edits cancel requests, retain source facts, keep input focus and hide old guidance", async () => {
    putCase({ father_alive: false }, [history(["father_alive"])]);
    const old = deferred<PlanningResult>();
    const middle = deferred<PlanningResult>();
    request.mockReturnValueOnce(old.promise).mockReturnValueOnce(middle.promise).mockResolvedValueOnce(plan());
    renderEnglish();
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
    expandDate();
    const input = screen.getByLabelText("Guidance date");
    input.focus();
    fireEvent.change(input, { target: { value: "2000-01-01" } });
    expect(request.mock.calls[0][1].aborted).toBe(true);
    expect(input).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Use this date" }));
    expect(request.mock.calls[1][0]).toMatchObject({ facts: { father_alive: false }, evaluation_context: { evaluation_date: "2000-01-01" } });
    fireEvent.change(input, { target: { value: "2001-01-01" } });
    expect(request.mock.calls[1][1].aborted).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Use this date" }));
    await screen.findByText("Authored preparation plan");
    expect(screen.getAllByText("2001-01-01").length).toBeGreaterThan(0);
    await act(async () => { old.resolve(plan()); middle.resolve(plan()); });
    expect(screen.queryByText("2000-01-01")).not.toBeInTheDocument();
    expect(stored().date).toBe("2001-01-01");
    fireEvent.change(input, { target: { value: "2002-01-01" } });
    expect(screen.queryByText("Authored preparation plan")).not.toBeInTheDocument();
  });
  it("regenerates for local today with the current facts, not the original empty request", async () => {
    putCase({ father_alive: false }, [history(["father_alive"])]);
    request.mockResolvedValue(plan());
    renderEnglish();
    await screen.findByText("Authored preparation plan");
    fireEvent.click(screen.getByRole("button", { name: "Regenerate for today" }));
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2));
    expect(request.mock.calls[1][0]).toMatchObject({ facts: { father_alive: false }, evaluation_context: { evaluation_date: localToday() } });
  });
  it("aborts on unmount and does not double-submit while a request is pending", async () => {
    const pending = deferred<PlanningResult>();
    request.mockResolvedValueOnce(next()).mockReturnValueOnce(pending.promise);
    const mounted = renderEnglish();
    fireEvent.click(await screen.findByRole("radio", { name: "No" }));
    const button = continueButton();
    act(() => { button.click(); button.click(); });
    expect(request).toHaveBeenCalledTimes(2);
    const loading = screen.getByText("Checking your answers…");
    expect(loading).toHaveAttribute("role", "status");
    // An aria-busy ancestor would defer this live announcement until it is gone.
    expect(loading.closest('[aria-busy="true"]')).toBeNull();
    mounted.unmount();
    expect(request.mock.calls[1][1].aborted).toBe(true);
    await act(async () => pending.resolve(plan()));
  });
  it("continues in memory when storage is blocked across locale remounts, isolates Services and clears", async () => {
    vi.spyOn(window, "sessionStorage", "get").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); });
    request.mockResolvedValueOnce(next()).mockResolvedValueOnce(plan()).mockResolvedValueOnce({ type: "inconclusive", reason: "unsupported", message: "رسالة مؤلفة" });
    const mounted = renderEnglish();
    await chooseNo();
    await screen.findByText("Authored preparation plan");
    expect(screen.getByText(/Tab storage isn’t available/)).toBeInTheDocument();
    mounted.unmount();
    const translated = render(<Questionnaire service={service} locale="ar" />);
    await screen.findByText("رسالة مؤلفة");
    expect(request.mock.calls[2][0].facts).toEqual({ father_alive: false });
    const other = { ...service, id: "service.other" };
    request.mockResolvedValueOnce({ type: "inconclusive", reason: "unsupported", message: "رسالة الخدمة الأخرى" });
    translated.unmount();
    const otherMount = render(<Questionnaire service={other} locale="ar" />);
    await screen.findByText("رسالة الخدمة الأخرى");
    expect(request.mock.calls[3][0]).toMatchObject({ service_id: other.id, facts: {} });
    fireEvent.click(screen.getByRole("button", { name: "امسح الإجابات وابدأ من جديد" }));
    fireEvent.click(screen.getByRole("button", { name: "أيوه، امسح الإجابات" }));
    expect(screen.getByText(/ما قدرناش نمسح تخزين المتصفح/)).toBeInTheDocument();
    otherMount.unmount();
    renderEnglish();
    await screen.findByRole("heading", { name: "Is your father alive?" });
    expect(request.mock.calls[4][0]).toMatchObject({ service_id: service.id, facts: {} });
  });
  it("keeps submitted facts after quota failure and removes any older saved copy", async () => {
    request.mockResolvedValueOnce(next()).mockRejectedValueOnce(new ApiError("network"));
    renderEnglish();
    await screen.findByRole("heading", { name: "Is your father alive?" });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("quota", "QuotaExceededError"); });
    await chooseNo();
    await screen.findByRole("heading", { name: "We couldn’t continue" });
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    expect(screen.getByText(/Tab storage isn’t available/)).toBeInTheDocument();
    review();
    expect(screen.getByRole("button", { name: "Change answer: Father is alive" })).toBeEnabled();
  });
  it("does not render a response for a different Service", async () => {
    request.mockResolvedValue(plan("service.other"));
    renderEnglish();
    await screen.findByRole("heading", { name: "We couldn’t continue" });
    expect(screen.queryByText("Authored preparation plan")).not.toBeInTheDocument();
  });
});

describe("manual recovery, rate limits and local printing", () => {
  it.each(["network", "unavailable", "rate_limited", "unexpected_response"] as const)("preserves answers for %s and retries manually without logging", async (kind) => {
    const log = vi.spyOn(console, "log").mockImplementation(() => {});
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    request.mockResolvedValueOnce(next()).mockRejectedValueOnce(new ApiError(kind)).mockResolvedValueOnce(plan());
    renderEnglish();
    await chooseNo();
    await screen.findByRole("heading", { name: "We couldn’t continue" });
    expect(stored().facts).toEqual({ father_alive: false });
    expect(request).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("button", { name: "Clear answers and start again" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Try again with these answers" }));
    await screen.findByText("Authored preparation plan");
    expect(request.mock.calls[2][0]).toEqual(request.mock.calls[1][0]);
    expect(log).not.toHaveBeenCalled();
    expect(warn).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });
  it.each(["rate_limited", "unavailable"] as const)("honors Retry-After for %s without an automatic retry, including locale changes", async (kind) => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-01T12:00:00"));
    request.mockRejectedValueOnce(new ApiError(kind, 2)).mockResolvedValueOnce(plan());
    let mounted!: ReturnType<typeof renderEnglish>;
    await act(async () => { mounted = renderEnglish(); });
    expect(screen.getByRole("button", { name: "Try again with these answers" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Regenerate for today" })).toBeDisabled();
    await act(async () => { vi.advanceTimersByTime(500); });
    mounted.unmount();
    let translated!: ReturnType<typeof render>;
    await act(async () => { translated = render(<Questionnaire service={service} locale="ar" />); });
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "جرّب تاني بنفس الإجابات" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent(kind === "unavailable" ? "بردي مش متاح مؤقتًا" : "في طلبات كتير اتبعتت");
    await act(async () => { vi.advanceTimersByTime(1499); });
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "جرّب تاني بنفس الإجابات" })).toBeDisabled();
    await act(async () => { vi.advanceTimersByTime(1); });
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "جرّب تاني بنفس الإجابات" })).toBeEnabled();
    translated.unmount();
    await act(async () => { renderEnglish(); });
    expect(request).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Try again with these answers" })).toBeEnabled();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Try again with these answers" })); });
    expect(request).toHaveBeenCalledTimes(2);
  });
  it("reset remains available during a retry delay without bypassing it", async () => {
    vi.useFakeTimers();
    request.mockRejectedValueOnce(new ApiError("rate_limited", 2)).mockResolvedValueOnce(next());
    await act(async () => { renderEnglish(); });
    fireEvent.click(screen.getByRole("button", { name: "Clear answers and start again" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, clear answers" }));
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).toBeNull();
    expect(screen.getByRole("button", { name: "Start again" })).toBeDisabled();
    await act(async () => { vi.advanceTimersByTime(2000); });
    expect(request).toHaveBeenCalledTimes(1);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Start again" })); });
    expect(request.mock.calls[1][0].facts).toEqual({});
  });
  it("keeps facts out of localStorage, cookies and URLs, and sanitizes unknown failures", async () => {
    const local = vi.spyOn(window, "localStorage", "get").mockImplementation(() => { throw new Error("not permitted"); });
    const cookie = vi.spyOn(document, "cookie", "set");
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const href = window.location.href;
    const sensitive = "must-not-appear-in-errors-or-observability";
    putCase({ residence_district: sensitive }, [history(["residence_district"])]);
    request.mockRejectedValue(new Error(sensitive));
    renderEnglish();
    await screen.findByRole("heading", { name: "We couldn’t continue" });
    expect(screen.getByRole("alert")).not.toHaveTextContent(sensitive);
    expect(local).not.toHaveBeenCalled();
    expect(cookie).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
    expect(window.location.href).toBe(href);
  });
  it("shows the exact localized inconclusive message and recovery, not success", async () => {
    const message = "رسالة مؤلفة كما هي.\nبدون تخمين.";
    request.mockResolvedValue({ type: "inconclusive", reason: "unsupported_case", message });
    const { container } = render(<Questionnaire service={service} locale="ar" />);
    await screen.findByRole("heading", { name: "مش قادرين نجهّز إرشادات موثوقة دلوقتي" });
    expect(container.querySelector(".planning-authored")?.textContent).toBe(message);
    expect(screen.getByRole("button", { name: "جرّب تاني بنفس الإجابات" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "اطبع الإرشادات" })).not.toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toHaveClass("planning-stage"));
  });
  it("uses browser print with the real PlanView date, warnings and non-collapsible sources", async () => {
    putCase({ father_alive: false }, [history(["father_alive"])]);
    const result = plan();
    result.warnings = [{
      id: "warning.test", text: "Authored warning — do not omit", kind: "administrative", severity: "important", role: "limitation",
      freshness: { state: "current", verified_on: "2020-02-01", reverify_on: null },
      sources: [{ id: "source.test", authority_id: "authority.test", title: "Authored official source", locator: "https://example.gov.eg/source", classification: "official", retrieved_on: "2020-02-01" }],
    }];
    request.mockResolvedValue(result);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    const { container } = renderEnglish();
    await screen.findByText("Authored preparation plan");
    expect(screen.getAllByText("2020-02-29").length).toBeGreaterThan(0);
    expect(screen.getByText("Authored warning — do not omit")).toBeInTheDocument();
    expect(Array.from(container.querySelectorAll(".plan-print-only")).some((node) => node.textContent?.includes("Authored official source"))).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Print guidance" }));
    expect(print).toHaveBeenCalledOnce();
    expect(request).toHaveBeenCalledOnce();
    expect(container.querySelector(".plan-view")?.closest(".planning-controls")).toBeNull();
    for (const control of container.querySelectorAll(".planning-date, .planning-review, .planning-print-actions, .planning-case-tools")) expect(control.closest(".planning-controls")).not.toBeNull();
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).not.toContain("Authored warning");
    expect(sessionStorage.getItem(CASE_STORAGE_KEY)).not.toContain("source.test");
  });
});
