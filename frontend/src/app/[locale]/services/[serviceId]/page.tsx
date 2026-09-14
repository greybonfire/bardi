import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Arrow, ServiceUnavailable } from "@/components/service-directory";
import { servicesForPage } from "@/lib/service-pages";
import { isLocale, pageAlternates, servicePath, siteCopy } from "@/lib/site";

type Props = { params: Promise<{ locale: string; serviceId: string }> };
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale, serviceId } = await params;
  if (!isLocale(locale)) return {};
  const result = await servicesForPage();
  const service = result.ok ? result.services.find(({ id }) => id === serviceId) : undefined;
  return { title: service?.title[locale], description: service ? `${service.title[locale]}. ${siteCopy(locale).description}` : undefined,
    alternates: pageAlternates(`/services/${encodeURIComponent(serviceId)}`, locale), robots: service ? undefined : { index: false } };
}

export default async function ServicePage({ params }: Props) {
  const { locale, serviceId } = await params;
  if (!isLocale(locale)) notFound();
  const t = siteCopy(locale);
  const result = await servicesForPage();
  if (!result.ok) return <ServiceUnavailable locale={locale} />;
  const service = result.services.find(({ id }) => id === serviceId);
  if (!service) notFound();
  return <article className="reading-page service-intro">
    <Link className="back-link" href={`/${locale}`} prefetch={false}>{t.allServices}</Link>
    <h1>{service.title[locale]}</h1>
    <section><h2>{t.before}</h2><p className="lead">{t.beforeIntro}</p></section>
    <div className="start-action stack"><div className="actions"><Link className="button" href={`${servicePath(locale, service.id)}/plan`} prefetch={false}>{t.start}<Arrow /></Link></div><p className="muted">{t.beginHint}</p></div>
    <section><h2>{t.preparation}</h2><p>{t.expect}</p><p>{t.noApplication}</p></section>
    <section className="service-privacy"><h2>{t.tab}</h2><p>{t.tabHint}</p><Link href={`/${locale}/privacy`} prefetch={false}>{t.privacy}</Link></section>
  </article>;
}
