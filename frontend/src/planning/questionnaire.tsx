"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { Locale, PlanningResult, Service } from "@/api/contract";
import { ApiError, requestPlan } from "@/api/client";
import { PlanView } from "@/components/plan-view";
import { copy } from "./copy";
import { answerLabel, fieldLabel } from "./labels";
import { QuestionForm } from "./question-form";
import { correctDiagnostics, diagnosticDate, diagnosticKeys, freshCase, isCalendarDate, localToday, questionProblem, rewindCase } from "./state";
import type { ActiveCase } from "./state";
import type { StorageNotice } from "./storage";
import { attachTabCase } from "./tab-case";
import type { CaseAttachment } from "./tab-case";
import "./questionnaire.css";

type FailureKind = ApiError["kind"];
type View =
  | { status: "initializing" }
  | { status: "loading" | "idle" | "date_edit" | "configuration"; locale: Locale }
  | { status: "failure"; locale: Locale; kind: FailureKind }
  | { status: "result"; locale: Locale; result: PlanningResult; date: string; requestId: number };

export function Questionnaire({ service, locale = "ar" }: { service: Service; locale?: Locale }) {
  // A different Service never inherits the in-memory case, even if storage is blocked.
  return <QuestionnaireCase key={service.id} service={service} locale={locale} />;
}

function QuestionnaireCase({ service, locale }: { service: Service; locale: Locale }) {
  const t = copy(locale);
  const id = useId();
  const [active, setActive] = useState<ActiveCase | null>(null);
  const [view, setView] = useState<View>({ status: "initializing" });
  const [notice, setNotice] = useState<StorageNotice>(null);
  const [dateDraft, setDateDraft] = useState("");
  const [dateError, setDateError] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const [retryUntil, setRetryUntil] = useState(0);
  const [clock, setClock] = useState(() => Date.now());
  const attachmentRef = useRef<CaseAttachment | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const sequence = useRef(0);
  const panelRef = useRef<HTMLElement>(null);
  const dateRef = useRef<HTMLInputElement>(null);
  const dateDetailsRef = useRef<HTMLDetailsElement>(null);
  const clearRef = useRef<HTMLButtonElement>(null);
  const confirmationRef = useRef<HTMLDivElement>(null);

  const cancelRequest = useCallback(() => {
    sequence.current += 1;
    requestRef.current?.abort();
    requestRef.current = null;
  }, []);

  const commitCase = useCallback((next: ActiveCase) => {
    const attachment = attachmentRef.current;
    if (!attachment?.isCurrent()) return;
    const tab = attachment.state;
    tab.active = next;
    if (!tab.storage.save(next)) tab.notice = "memory";
    setActive(next);
    setDateDraft(next.date);
    setDateError(false);
    setNotice(tab.notice);
  }, []);

  const run = useCallback((next: ActiveCase, language: Locale) => {
    const attachment = attachmentRef.current;
    if (!attachment?.isCurrent()) return;
    const tab = attachment.state;
    cancelRequest();
    if (Date.now() < tab.retryUntil) {
      setView({ status: "failure", locale: language, kind: tab.failure ?? "rate_limited" });
      return;
    }
    tab.failure = null;
    tab.retryUntil = 0;
    setRetryUntil(0);
    const controller = new AbortController();
    requestRef.current = controller;
    const requestId = sequence.current;
    setView({ status: "loading", locale: language });
    void requestPlan({
      service_id: next.serviceId, facts: next.facts, locale: language,
      evaluation_context: { evaluation_date: next.date },
    }, controller.signal).then((result) => {
      // Guard identity as well as AbortSignal: a transport/mock may ignore abort.
      if (!attachment.isCurrent() || controller.signal.aborted || sequence.current !== requestId) return;
      requestRef.current = null;
      if ((result.type === "next_question" || result.type === "plan") && result.service_id !== next.serviceId) {
        tab.failure = "unexpected_response";
        setView({ status: "failure", locale: language, kind: "unexpected_response" });
      } else if (result.type === "next_question" && questionProblem(result.question, next.facts)) {
        setView({ status: "configuration", locale: language });
      } else {
        setView({ status: "result", locale: language, result, date: next.date, requestId });
      }
    }).catch((error: unknown) => {
      if (!attachment.isCurrent() || controller.signal.aborted || sequence.current !== requestId) return;
      requestRef.current = null;
      const kind = error instanceof ApiError ? error.kind : "unexpected_response";
      const delay = error instanceof ApiError && error.retryAfter !== null && Number.isFinite(error.retryAfter)
        ? Math.max(0, error.retryAfter) : 0;
      const now = Date.now();
      tab.retryUntil = now + delay * 1000;
      tab.failure = kind;
      setClock(now);
      setRetryUntil(tab.retryUntil);
      setView({ status: "failure", locale: language, kind });
    });
  }, [cancelRequest]);

  useEffect(() => {
    // SSR and the first hydration render never touch the browser-only owner.
    // Acquiring it invalidates any old mount, including ignored AbortSignals.
    const attachment = attachTabCase(service.id, cancelRequest);
    attachmentRef.current = attachment;
    const tab = attachment.state;
    // This external browser snapshot must initialize after hydration, not in an
    // SSR render. The one extra render also removes the plain no-JS recovery.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setActive(tab.active);
    setNotice(tab.notice);
    setDateDraft(tab.active.date);
    setDateError(false);
    setClock(Date.now());
    setRetryUntil(tab.retryUntil);
    if (tab.idle) setView({ status: "idle", locale });
    else if (tab.failure) setView({ status: "failure", locale, kind: tab.failure });
    else run(tab.active, locale);
    return attachment.release;
  }, [service.id, locale, run, cancelRequest]);

  useEffect(() => {
    if (!retryUntil) return;
    // This timer only enables a manual action. It never sends a request. Schedule
    // against the deadline independently of React paint timing/background tabs.
    let timeout: number;
    const tick = () => {
      const now = Date.now();
      setClock(now);
      if (now < retryUntil) timeout = window.setTimeout(tick, Math.min(1000, retryUntil - now));
    };
    timeout = window.setTimeout(tick, Math.max(0, Math.min(1000, retryUntil - Date.now())));
    return () => window.clearTimeout(timeout);
  }, [retryUntil]);

  useEffect(() => {
    if (view.status !== "initializing" && view.status !== "loading" && view.status !== "date_edit" && view.locale === locale) panelRef.current?.focus();
  }, [view, locale]);

  useEffect(() => { if (confirmClear) confirmationRef.current?.focus(); }, [confirmClear]);

  const current = view.status !== "initializing" && view.locale === locale;
  const busy = !current || view.status === "loading";
  const waiting = retryUntil > clock;
  const remaining = Math.max(0, Math.ceil((retryUntil - clock) / 1000));
  const result = current && view.status === "result" ? view.result : null;
  const isPlan = result?.type === "plan";

  function advance(next: ActiveCase) {
    const attachment = attachmentRef.current;
    if (!attachment?.isCurrent()) return;
    attachment.state.idle = false;
    commitCase(next);
    run(next, locale);
  }
  function submit(next: ActiveCase) {
    // A ref closes the interval before React paints the disabled/loading state.
    const attachment = attachmentRef.current;
    if (!attachment?.isCurrent() || requestRef.current || Date.now() < attachment.state.retryUntil) return;
    advance(next);
  }
  function editDate() {
    cancelRequest();
    setView({ status: "date_edit", locale });
  }
  function clearCase() {
    const attachment = attachmentRef.current;
    if (!attachment?.isCurrent()) return;
    cancelRequest();
    const tab = attachment.state;
    const next = freshCase(service.id);
    tab.idle = true;
    tab.active = next;
    tab.notice = tab.storage.clear() ? null : "clear_failed";
    setActive(next);
    setDateDraft(next.date);
    setDateError(false);
    setNotice(tab.notice);
    setConfirmClear(false);
    setView({ status: "idle", locale });
  }

  const retry = <button type="button" className="button" disabled={busy || waiting} onClick={() => {
    if (attachmentRef.current) submit(attachmentRef.current.state.active);
  }}>{t.retry}</button>;

  return <div className="planning stack" lang={locale} dir={locale === "ar" ? "rtl" : "ltr"}>
    <div className="planning-controls planning-settings stack">
      <details className="planning-disclosure planning-privacy">
        <summary>{t.privacySummary}</summary>
        <p className="muted">{t.privacy}</p>
      </details>
      {active && <details ref={dateDetailsRef} className="planning-disclosure">
        <summary>{t.date}: <time dateTime={active.date} dir="ltr">{active.date}</time></summary>
        <form className="planning-date" noValidate onSubmit={(event) => {
          event.preventDefault();
          if (!isCalendarDate(dateDraft)) {
            setDateError(true);
            dateRef.current?.focus();
            return;
          }
          if (!waiting && !(requestRef.current && dateDraft === attachmentRef.current?.state.active.date)) advance({ ...active, date: dateDraft });
        }}>
          <label className="planning-field-label" htmlFor={`${id}-date`}>{t.date}</label>
          <p id={`${id}-date-hint`} className="muted planning-field-hint">{t.dateHint}</p>
          <div className="actions">
            <input ref={dateRef} className="planning-input planning-input-date" id={`${id}-date`} type="date"
              dir="ltr" min="0001-01-01" max="9999-12-31" value={dateDraft}
              aria-describedby={`${id}-date-hint${dateError ? ` ${id}-date-error` : ""}`} aria-invalid={dateError}
              onChange={(event) => { setDateDraft(event.target.value); setDateError(false); editDate(); }} />
            <button className="button-secondary" type="submit" disabled={waiting || (busy && dateDraft === active.date)}>{t.useDate}</button>
          </div>
          {dateError && <p id={`${id}-date-error`} className="planning-field-error" role="alert">{t.dateError}</p>}
        </form>
      </details>}
      {notice && <p className="notice" role="status">{t[notice]}</p>}
      {waiting && <p className="notice" role="status">{t.wait} {new Intl.NumberFormat(locale).format(remaining)} {t.seconds}</p>}
    </div>

    <section ref={panelRef} tabIndex={-1} className={`planning-stage${isPlan ? "" : " planning-controls"}`} data-loading={busy}>
      {view.status === "initializing" ? <div className="notice stack">
        <p>{t.javascript}</p><p>{t.javascriptRecovery}</p>
        <a href={`/${locale}/services/${encodeURIComponent(service.id)}`}>{t.backToService}</a>
      </div> : busy && <p role="status" aria-live="polite" className="planning-loading">{t.loading}</p>}
      {current && view.status === "idle" && <div className="stack">
        <h2>{t.cleared}</h2><p>{t.clearedHint}</p>
        <div className="actions"><button className="button" disabled={waiting} onClick={() => active && submit(active)}>{t.start}</button></div>
      </div>}
      {current && view.status === "date_edit" && <div className="stack"><h2>{t.dateEditing}</h2><p>{t.dateEditingHint}</p></div>}
      {current && view.status === "failure" && <div className="notice planning-error stack" role="alert">
        <h2>{t.failure}</h2><p>{t[view.kind]}</p><div className="actions">{retry}</div>
      </div>}
      {current && view.status === "configuration" && <div className="notice planning-error stack" role="alert">
        <h2>{t.configuration}</h2><p>{t.configurationHint}</p><div className="actions">{retry}</div>
      </div>}
      {result?.type === "next_question" && active && view.status === "result" && <QuestionForm
        key={`${view.requestId}:${locale}`} question={result.question} active={active} locale={locale}
        disabled={busy || waiting} onAnswer={submit} />}
      {result?.type === "inconclusive" && <div className="notice stack">
        <h2>{t.inconclusive}</h2><p className="planning-authored">{result.message}</p><p>{t.inconclusiveHint}</p>
        <div className="actions">{retry}</div>
      </div>}
      {result?.type === "invalid" && <div className="notice planning-error stack" role="alert">
        <h2>{t.invalid}</h2>
        <p>{result.diagnostics.some(({ code }) => code === "contradictory_facts") ? t.contradictory : diagnosticKeys(result).length ? t.invalidHint : t.invalidGeneral}</p>
        {diagnosticKeys(result).length > 0 && <>
          <ul>{diagnosticKeys(result).map((key) => <li key={key}><bdi>{fieldLabel(key, locale)}</bdi></li>)}</ul>
          <div className="actions"><button type="button" className="button" disabled={waiting} onClick={() => {
            if (active) advance(correctDiagnostics(active, diagnosticKeys(result)));
          }}>{t.correct}</button></div>
        </>}
        {diagnosticDate(result) && <button type="button" className="button-secondary" onClick={() => {
          if (dateDetailsRef.current) dateDetailsRef.current.open = true;
          editDate();
          dateRef.current?.focus();
        }}>{t.correctDate}</button>}
        {!diagnosticKeys(result).length && !diagnosticDate(result) && <div className="actions">{retry}</div>}
      </div>}
      {result?.type === "plan" && view.status === "result" && <>
        <div className="planning-controls planning-print-actions stack">
          <div className="actions"><button type="button" className="button-secondary" onClick={() => window.print()}>{t.print}</button></div>
          <p className="muted">{t.printHint}</p>
        </div>
        <PlanView plan={result} locale={locale} evaluationDate={view.date} />
      </>}
    </section>

    {active && <div className="planning-controls planning-case-tools stack">
      {active.history.length > 0 && <details className="planning-review">
        <summary>{t.review}</summary><p className="muted">{t.reviewHint}</p>
        <ul>{active.history.map((entry, index) => {
          // A recurring multi-Fact question can share keys with earlier entries.
          // Show each value once, at its earliest correction point.
          const earlier = new Set(active.history.slice(0, index).flatMap(({ keys }) => keys));
          const keys = entry.keys.filter((key) => Object.hasOwn(active.facts, key) && !earlier.has(key));
          return keys.length > 0 && <li key={`${entry.questionId}:${index}`}>
            <dl>{keys.map((key) => <div key={key}><dt><bdi>{fieldLabel(key, locale)}</bdi></dt>
              <dd><bdi>{active.facts[key] === "" ? t.emptyValue : answerLabel(key, active.facts[key], locale)}</bdi></dd></div>)}</dl>
            <button type="button" className="planning-text-button" aria-label={`${t.change}: ${keys.map((key) => fieldLabel(key, locale)).join(locale === "ar" ? "، " : ", ")}`}
              onClick={() => { if (attachmentRef.current?.state.active === active) advance(rewindCase(active, index)); }}>{t.change}</button>
          </li>;
        })}</ul>
      </details>}
      {current && view.status !== "idle" && <div className="actions">
        <button type="button" className="button-secondary" disabled={waiting || busy} onClick={() => {
          if (!requestRef.current) advance({ ...active, date: localToday() });
        }}>{t.today}</button>
      </div>}
      {!confirmClear ? <div className="actions"><button type="button" className="planning-text-button" ref={clearRef}
        onClick={() => setConfirmClear(true)}>{t.clear}</button></div> : <div ref={confirmationRef} className="notice stack" tabIndex={-1}>
        <h2>{t.clearTitle}</h2><p>{t.clearHint}</p>
        <div className="actions">
          <button type="button" className="button" onClick={clearCase}>{t.confirmClear}</button>
          <button type="button" className="button-secondary" onClick={() => { setConfirmClear(false); window.requestAnimationFrame(() => clearRef.current?.focus()); }}>{t.cancelClear}</button>
        </div>
      </div>}
    </div>}
  </div>;
}
