"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Locale, Question } from "@/api/contract";
import { copy } from "./copy";
import { answerLabel, fieldLabel } from "./labels";
import { prefill, submitAnswers } from "./state";
import type { ActiveCase, AnswerErrors, Draft, FieldError } from "./state";

export function QuestionForm({ question, active, locale, disabled, onAnswer }: {
  question: Question;
  active: ActiveCase;
  locale: Locale;
  disabled: boolean;
  onAnswer: (active: ActiveCase) => void;
}) {
  const t = copy(locale);
  const id = useId();
  const [draft, setDraft] = useState<Draft>(() => prefill(question, active.facts));
  const [errors, setErrors] = useState<AnswerErrors | null>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  const multiple = question.answers.length > 1;
  const fieldError = (error: FieldError): string => error === "minimum" ? t.minimumError : error === "date" ? t.dateError : t[error];

  useEffect(() => { if (errors) errorRef.current?.focus(); }, [errors]);

  function update(key: string, value: string | boolean | undefined) {
    setDraft((previous) => Object.fromEntries([
      ...Object.entries(previous).filter(([existing]) => existing !== key),
      ...(value === undefined ? [] : [[key, value]]),
    ]));
    setErrors(null);
  }

  return (
    <form className="planning-question stack" noValidate autoComplete="off" onSubmit={(event) => {
      event.preventDefault();
      if (disabled) return;
      const result = submitAnswers(active, question, draft);
      if ("errors" in result) setErrors(result.errors);
      else onAnswer(result.active);
    }} aria-labelledby={`${id}-question`}>
      <h2 id={`${id}-question`}>{question.text}</h2>
      {multiple && <p className="muted">{t.multiHint}</p>}
      {errors && <div className="notice planning-error" role="alert" tabIndex={-1} ref={errorRef}>
        <h3>{t.errors}</h3>
        {errors.form && <p>{t[errors.form]}</p>}
        {Object.keys(errors.fields).length > 0 && <ul>{question.answers.map(({ key }, index) => Object.hasOwn(errors.fields, key) && (
          <li key={key}><a href={`#${id}-field-${index}`} onClick={(event) => {
            event.preventDefault();
            document.getElementById(`${id}-field-${index}`)?.focus();
          }}>{fieldLabel(key, locale)}: {fieldError(errors.fields[key])}</a></li>
        ))}</ul>}
      </div>}
      {question.answers.map((answer, index) => {
        const fieldId = `${id}-field-${index}`;
        const hasValue = Object.hasOwn(draft, answer.key);
        const value = hasValue ? draft[answer.key] : undefined;
        const error = errors && Object.hasOwn(errors.fields, answer.key) ? errors.fields[answer.key] : null;
        const label = multiple ? fieldLabel(answer.key, locale) : question.text;
        const hint = answer.kind === "integer" ? `${t.integerHint}${answer.minimum === null ? "" : ` ${t.minimum} ${answer.minimum}`}`
          : answer.kind === "date" ? t.dateFieldHint : answer.kind === "string" ? t.stringHint : null;
        const describedBy = [hint && `${fieldId}-hint`, error && `${fieldId}-error`].filter(Boolean).join(" ") || undefined;
        const choices = answer.kind === "boolean" ? [true, false] : answer.kind === "enum" ? answer.enum_options : null;
        return <div className="planning-field" key={answer.key}>
          {choices ? <fieldset disabled={disabled} aria-describedby={describedBy} aria-invalid={!!error}>
            <legend className={multiple ? "planning-field-label" : "planning-visually-hidden"}>{label}</legend>
            <div className="planning-choices">{choices.map((choice, optionIndex) => <label className="planning-choice" key={String(choice)}>
              <input type="radio" id={optionIndex === 0 ? fieldId : `${fieldId}-${optionIndex}`} name={fieldId}
                value={String(choice)} checked={hasValue && value === choice} onChange={() => update(answer.key, choice)} />
              <span dir="auto">{answerLabel(answer.key, choice, locale)}</span>
            </label>)}</div>
          </fieldset> : <>
            <label className={multiple ? "planning-field-label" : "planning-visually-hidden"} htmlFor={fieldId}>{label}</label>
            {hint && <p className="muted planning-field-hint" id={`${fieldId}-hint`}>{hint}</p>}
            <input className={`planning-input planning-input-${answer.kind}`} id={fieldId} name={fieldId}
              type={answer.kind === "date" ? "date" : "text"}
              inputMode={answer.kind === "integer" ? "numeric" : undefined}
              min={answer.kind === "date" ? "0001-01-01" : undefined}
              max={answer.kind === "date" ? "9999-12-31" : undefined}
              dir={answer.kind === "string" ? "auto" : "ltr"}
              value={typeof value === "string" ? value : ""} disabled={disabled}
              aria-invalid={!!error} aria-describedby={describedBy}
              onChange={(event) => update(answer.key, event.target.value === "" && answer.kind !== "string" ? undefined : event.target.value)} />
          </>}
          {error && <p className="planning-field-error" id={`${fieldId}-error`}>{fieldError(error)}</p>}
          {multiple && hasValue && <button type="button" className="planning-text-button" disabled={disabled}
            aria-label={`${t.omit}: ${fieldLabel(answer.key, locale)}`} onClick={() => update(answer.key, undefined)}>{t.omit}</button>}
        </div>;
      })}
      <div className="actions"><button type="submit" className="button" disabled={disabled}>{t.continue}</button></div>
    </form>
  );
}
