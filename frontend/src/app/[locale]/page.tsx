import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { ServiceDirectory, ServiceUnavailable } from "@/components/service-directory";
import { servicesForPage } from "@/lib/service-pages";
import { isLocale, pageAlternates, siteCopy } from "@/lib/site";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { alternates: pageAlternates("", locale) } : {};
}

export default async function Home({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = siteCopy(locale);
  const result = await servicesForPage();
  return <>
    <div className="home-intro"><h1>{t.title}</h1><p className="lead">{t.intro}</p></div>
    <div className="home-columns">
      <section className="directory" aria-labelledby="services-title">
        <h2 id="services-title">{t.services}</h2><p className="muted">{t.servicesHint}</p>
        {result.ok ? <ServiceDirectory services={result.services} locale={locale} /> : <ServiceUnavailable locale={locale} />}
      </section>
      <aside className="guidance-note stack" aria-labelledby="guidance-title">
        <h2 id="guidance-title">{t.guidance}</h2><p>{t.guidanceBody}</p><p>{t.guidanceLimits}</p>
      </aside>
    </div>
  </>;
}
