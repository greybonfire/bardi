import type { Metadata } from "next";
import Link from "next/link";
import "@fontsource/noto-sans-arabic/arabic-400.css";
import "@fontsource/noto-sans-arabic/arabic-700.css";
import "@fontsource/source-sans-3/latin-400.css";
import "./globals.css";

export const metadata: Metadata = { title: "بردي — الصفحة مش موجودة", robots: { index: false } };
export default function GlobalNotFound() {
  return <html lang="ar" dir="rtl"><body><main className="site-main reading-page stack"><h1>الصفحة مش موجودة</h1><p>ارجع للخدمات المتاحة عشان تكمّل.</p><Link href="/ar" prefetch={false}>كل الخدمات</Link><p lang="en" dir="ltr">Page not found. <Link href="/en" prefetch={false}>Browse services in English</Link>.</p></main></body></html>;
}
