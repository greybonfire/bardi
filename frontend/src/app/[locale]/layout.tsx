import type { Metadata } from "next";
import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SandboxNotice } from "@/components/sandbox-notice";
import { isLocale, siteCopy, siteOrigin } from "@/lib/site";
import "@fontsource/noto-sans-arabic/arabic-400.css";
import "@fontsource/noto-sans-arabic/arabic-600.css";
import "@fontsource/noto-sans-arabic/arabic-700.css";
import "@fontsource/source-sans-3/latin-400.css";
import "@fontsource/source-sans-3/latin-600.css";
import "@fontsource/source-sans-3/latin-700.css";
import "../globals.css";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const t = siteCopy(locale);
  return { metadataBase: new URL(siteOrigin()), title: { default: `${t.brand} — ${t.title}`, template: `%s | ${t.brand}` }, description: t.description, referrer: "no-referrer", applicationName: t.brand };
}

export default async function LocaleLayout({ children, params }: { children: React.ReactNode; params: Promise<{ locale: string }> }) {
  // Keep a root document for the locale page's notFound() boundary to render in.
  const { locale: requestedLocale } = await params;
  const locale = isLocale(requestedLocale) ? requestedLocale : "ar";
  const t = siteCopy(locale);
  return <html lang={locale} dir={locale === "ar" ? "rtl" : "ltr"}>
    <body>
      <a className="skip-link" href="#main-content">{t.skip}</a>
      <SiteHeader locale={locale} />
      <SandboxNotice locale={locale} />
      <main id="main-content" className="site-main" tabIndex={-1}>{children}</main>
      <footer className="site-footer"><div className="site-footer-inner">
        <p>{t.independent}</p><Link href={`/${locale}/privacy`} prefetch={false}>{t.privacy}</Link>
      </div></footer>
    </body>
  </html>;
}
