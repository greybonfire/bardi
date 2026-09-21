import "server-only";

import { connection } from "next/server";
import type { Locale } from "@/api/contract";

const copy = {
  ar: {
    title: "نسخة تجريبية محلية",
    detail: "دي بيانات منسوخة للتجربة المحلية بس. استبدال بيانات النسخة التجريبية بأمر refresh بيمسح تعديلات النسخة الحالية؛ إعادة تحميل الصفحة مش بتستبدل البيانات.",
  },
  en: {
    title: "Local questionnaire sandbox",
    detail: "Copied data for local testing only. The sandbox refresh command replaces the active copy and its changes; reloading this page does not replace data.",
  },
};

export async function SandboxNotice({ locale }: { locale: Locale }) {
  // Keep ordinary deployments static; only the sandbox needs request-time rendering.
  if (process.env.BARDI_SANDBOX !== "1") return null;
  await connection();

  const t = copy[locale];
  return <aside className="sandbox-notice" aria-label={t.title}>
    <p><strong>{t.title}.</strong> {t.detail}</p>
  </aside>;
}
