"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { siteCopy } from "@/lib/site";

// Deliberately never inspect or report the error object: rendered case data may be private.
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const { locale } = useParams();
  const language = locale === "en" ? "en" : "ar";
  const t = siteCopy(language);
  return <div className="reading-page stack" role="alert"><h1>{t.error}</h1><p>{t.errorHint}</p><div className="actions"><button className="button" onClick={reset}>{t.tryAgain}</button><Link href={`/${language}`} prefetch={false}>{t.allServices}</Link></div></div>;
}
