"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Locale } from "@/api/contract";
import { siteCopy } from "@/lib/site";

export function RetryServices({ locale }: { locale: Locale }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const t = siteCopy(locale);
  return <div className="actions"><button className="button-secondary" disabled={pending} onClick={() => startTransition(() => router.refresh())}>{pending ? t.loading : t.retry}</button></div>;
}
