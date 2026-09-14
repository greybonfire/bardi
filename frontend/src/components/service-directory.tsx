import Link from "next/link";
import type { Locale, Service } from "@/api/contract";
import { servicePath, siteCopy } from "@/lib/site";
import { RetryServices } from "./retry-services";

export function Arrow() {
  return <svg className="direction-arrow" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
}

export function ServiceDirectory({ services, locale }: { services: Service[]; locale: Locale }) {
  const t = siteCopy(locale);
  if (!services.length) return <div className="notice stack"><h3>{t.noServices}</h3><p>{t.noServicesHint}</p><RetryServices locale={locale} /></div>;
  return <ul className="service-list">{services.map((service) => <li key={service.id}>
    <Link href={servicePath(locale, service.id)} prefetch={false}><span>{service.title[locale]}</span><Arrow /></Link>
  </li>)}</ul>;
}

export function ServiceUnavailable({ locale }: { locale: Locale }) {
  const t = siteCopy(locale);
  return <section className="notice stack" role="status"><h2>{t.unavailable}</h2><p>{t.unavailableHint}</p><RetryServices locale={locale} /></section>;
}
