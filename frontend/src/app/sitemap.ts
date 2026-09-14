import type { MetadataRoute } from "next";
import { getServices } from "@/api/services.server";
import { servicePath, siteOrigin } from "@/lib/site";

export const dynamic = "force-dynamic";
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = siteOrigin();
  const result = await getServices();
  return (["ar", "en"] as const).flatMap((locale) => [
    { url: `${origin}/${locale}`, alternates: { languages: { ar: `${origin}/ar`, en: `${origin}/en` } } },
    { url: `${origin}/${locale}/privacy` },
    ...(result.ok ? result.services.map(({ id }) => ({
      url: `${origin}${servicePath(locale, id)}`,
      alternates: { languages: { ar: `${origin}${servicePath("ar", id)}`, en: `${origin}${servicePath("en", id)}` } },
    })) : []),
  ]);
}
