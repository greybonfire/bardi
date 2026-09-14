"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Locale } from "@/api/contract";
import { alternatePath, siteCopy } from "@/lib/site";

export function SiteHeader({ locale }: { locale: Locale }) {
  const pathname = usePathname();
  const t = siteCopy(locale);
  return <header className="site-header">
    <div className="site-header-inner">
      <Link href={`/${locale}`} className="wordmark" aria-label={`${t.brand} — ${t.allServices}`} prefetch={false}>
        <span lang="ar" dir="rtl">بردي</span><span lang="en" dir="ltr">bardi</span>
      </Link>
      <nav className="header-links" aria-label={locale === "ar" ? "التنقل الرئيسي" : "Main navigation"}>
        <Link className="services-link" href={`/${locale}`} prefetch={false}>{t.allServices}</Link>
        <Link href={alternatePath(pathname, locale)} hrefLang={locale === "ar" ? "en" : "ar"}
          lang={locale === "ar" ? "en" : "ar"} dir={locale === "ar" ? "ltr" : "rtl"}
          className="language-link" prefetch={false}>{locale === "ar" ? "English" : "العربية"}</Link>
      </nav>
    </div>
  </header>;
}
