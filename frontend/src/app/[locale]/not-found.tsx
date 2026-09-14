"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { siteCopy } from "@/lib/site";

export default function NotFound() {
  const { locale } = useParams();
  const language = locale === "en" ? "en" : "ar";
  const t = siteCopy(language);
  return <div className="reading-page stack"><h1>{t.missing}</h1><p className="lead">{t.missingHint}</p><Link href={`/${language}`} className="button" prefetch={false}>{t.allServices}</Link></div>;
}
