"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { Locale } from "@/api/contract";
import { copy } from "./copy";
import { clearTabCase } from "./tab-case";

// This control must not depend on a Service response or mount a questionnaire.
export function ClearTabCase({ locale }: { locale: Locale }) {
  const t = copy(locale);
  const id = useId();
  const [confirming, setConfirming] = useState(false);
  const [cleared, setCleared] = useState<boolean | null>(null);
  const button = useRef<HTMLButtonElement>(null);
  const confirmation = useRef<HTMLDivElement>(null);
  const result = useRef<HTMLParagraphElement>(null);

  useEffect(() => { if (confirming) confirmation.current?.focus(); }, [confirming]);
  useEffect(() => { if (cleared !== null) result.current?.focus(); }, [cleared]);

  return <section className="notice stack" aria-labelledby={`${id}-title`}>
    <h2 id={`${id}-title`}>{locale === "ar" ? "امسح إجابات التبويب ده" : "Clear this tab’s answers"}</h2>
    <p>{locale === "ar"
      ? "تقدر تمسح إجابات بردي من هنا حتى لو الخدمة مش متاحة أو اتشالت. المسح بيتم في المتصفح من غير ما نبعت إجاباتك للخادم."
      : "You can clear Bardi answers here even if a service is unavailable or has been removed. Clearing happens in this browser without sending your answers to the server."}</p>
    {!confirming ? <div className="actions"><button type="button" className="button-secondary" ref={button}
      onClick={() => { setCleared(null); setConfirming(true); }}>{t.clear}</button></div>
      : <div ref={confirmation} tabIndex={-1} className="stack">
        <h3>{t.clearTitle}</h3><p>{t.clearHint}</p>
        <div className="actions">
          <button type="button" className="button" onClick={() => {
            setCleared(clearTabCase());
            setConfirming(false);
          }}>{t.confirmClear}</button>
          <button type="button" className="button-secondary" onClick={() => {
            setConfirming(false);
            window.requestAnimationFrame(() => button.current?.focus());
          }}>{t.cancelClear}</button>
        </div>
      </div>}
    {cleared !== null && <p ref={result} tabIndex={-1} role="status">
      {cleared ? `${t.cleared}. ${t.clearedHint}` : t.clear_failed}
    </p>}
    <noscript><p>{locale === "ar"
      ? "لو أدوات المسح مش شغالة، امسح بيانات بردي من إعدادات المتصفح قبل ما تسيب جهاز مشترك."
      : "If these controls do not work, remove Bardi’s site data in your browser settings before leaving a shared device."}</p></noscript>
  </section>;
}
