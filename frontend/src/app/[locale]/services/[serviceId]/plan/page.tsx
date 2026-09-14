import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ServiceUnavailable } from "@/components/service-directory";
import { Questionnaire } from "@/planning/questionnaire";
import { servicesForPage } from "@/lib/service-pages";
import { isLocale, servicePath, siteCopy } from "@/lib/site";

type Props = { params: Promise<{ locale: string; serviceId: string }> };
export const dynamic = "force-dynamic";
export const metadata: Metadata = { robots: { index: false, follow: false, noarchive: true }, referrer: "no-referrer" };

export default async function PlanPage({ params }: Props) {
  const { locale, serviceId } = await params;
  if (!isLocale(locale)) notFound();
  const result = await servicesForPage();
  if (!result.ok) return <ServiceUnavailable locale={locale} />;
  const service = result.services.find(({ id }) => id === serviceId);
  if (!service) notFound();
  const t = siteCopy(locale);
  return <div className="questionnaire-page">
    <div className="questionnaire-heading"><Link className="back-link" href={servicePath(locale, serviceId)} prefetch={false}>{t.back}</Link><h1>{service.title[locale]}</h1></div>
    <Questionnaire service={service} locale={locale} />
  </div>;
}
