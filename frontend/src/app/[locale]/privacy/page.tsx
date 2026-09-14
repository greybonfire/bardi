import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ClearTabCase } from "@/planning/clear-tab-case";
import { isLocale, pageAlternates, siteCopy } from "@/lib/site";

type Props = { params: Promise<{ locale: string }> };
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { locale } = await params;
  return isLocale(locale) ? { title: siteCopy(locale).privacy, alternates: pageAlternates("/privacy", locale) } : {};
}
export default async function Privacy({ params }: Props) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const t = siteCopy(locale);
  return <article className="reading-page privacy-page">
    <Link className="back-link" href={`/${locale}`} prefetch={false}>{t.allServices}</Link><h1>{t.privacy}</h1>
    <ClearTabCase locale={locale} />
    {locale === "ar" ? <>
      <p className="lead">تقدر تستخدم بردي من غير حساب. بنسألك عن المعلومات اللي نحتاجها عشان نجهّز إرشادات، مش عشان نقدّم طلب بالنيابة عنك.</p>
      <h2>إيه اللي بيتحفظ هنا؟</h2>
      <p>إجاباتك اللي بعتها، والخدمة اللي اخترتها، وتاريخ الإرشادات، وترتيب الإجابات بيتحفظوا في تخزين جلسة التبويب ده في متصفحك. ده بيخلّيك تكمّل بعد تحديث الصفحة أو تغيير اللغة. بنحتفظ بحالة واحدة بس؛ بدء خدمة مختلفة بيستبدل الحالة السابقة.</p>
      <p>الأسئلة اللي لسه ما بعتّش إجاباتها ممكن تضيع مع تحديث الصفحة. لو المتصفح منع التخزين، هنقولك، وتقدر تكمّل في الصفحة من غير ضمان استرجاع التغييرات.</p>
      <h2>إيه اللي بيتبعت لبردي؟</h2>
      <p>لما تبدأ أو تبعت إجابة، بنبعت معرّف الخدمة، وإجاباتك، واللغة، وتاريخ الإرشادات لخادم بردي عشان يحسب الإرشادات. إجاباتك مش بتتحفظ كحالة على الخادم، ومش بنحطها في عنوان الصفحة.</p>
      <p>العميل ده مفيهوش تحليلات استخدام أو تسجيل جلسات أو أدوات تتبّع للإجابات. الإرشادات نفسها بتفضل في ذاكرة الصفحة، ومش بنحفظ نسخة منها في تخزين التبويب.</p>
      <h2>لو الجهاز مشترك</h2>
      <p>استخدم «امسح الإجابات وابدأ من جديد» هنا أو في صفحة الأسئلة قبل ما تمشي. قفل التبويب لوحده مش ضمان للمسح: بعض المتصفحات بترجّع الجلسات. لو ظهر إن المسح ما تمّش، امسح بيانات الموقع من إعدادات المتصفح.</p>
      <h2>الطباعة والروابط الخارجية</h2>
      <p>الطباعة أو الحفظ كملف PDF بيتم من متصفحك. النسخ دي ممكن تحتوي على معلومات شخصية، ومش بتتمسح لما تمسح إجاباتك من بردي. احتفظ بيها بأمان. روابط المصادر بتفتح مواقع مستقلة، ولكل موقع ممارساته الخاصة بالخصوصية.</p>
      <h2>اكتب المطلوب بس</h2>
      <p>ما تكتبش اسمك، أو رقمك القومي، أو بيانات تواصل في خانة مش بتطلبها. بردي دليل مستقل، مش جهة حكومية ولا بديل عن مراجعة الجهة المختصة.</p>
    </> : <>
      <p className="lead">You can use Bardi without an account. We ask for information needed to prepare guidance, not to submit an application on your behalf.</p>
      <h2>What stays in this tab?</h2>
      <p>Your submitted answers, selected service, guidance date, and answer order are kept in this browser tab’s session storage. This lets you continue after refreshing or changing language. Only one case is kept; starting a different service replaces the previous case.</p>
      <p>Unsubmitted answers may be lost on refresh. If your browser blocks storage, we’ll tell you. You can continue on the page, but your changes may not be recoverable.</p>
      <h2>What is sent to Bardi?</h2>
      <p>When you start or submit an answer, the service identifier, answers, language, and guidance date are sent to Bardi’s server to calculate guidance. Answers are not saved as a server-side case or placed in the page address.</p>
      <p>This client has no usage analytics, session recording, or answer-tracking tools. Guidance stays in page memory; we do not save it in tab storage.</p>
      <h2>On a shared device</h2>
      <p>Use “Clear answers and start again” here or on the questionnaire before leaving. Closing a tab alone does not guarantee deletion: some browsers restore sessions. If clearing fails, remove this site’s data through your browser settings.</p>
      <h2>Printing and external links</h2>
      <p>Printing or saving a PDF is handled by your browser. These copies may contain personal information and are not deleted when you clear your Bardi answers. Keep them safe. Source links open independent websites with their own privacy practices.</p>
      <h2>Enter only what is asked for</h2>
      <p>Do not enter your name, National ID number, or contact details in a field that does not ask for them. Bardi is an independent guide, not a government authority or a substitute for checking with the responsible authority.</p>
    </>}
  </article>;
}
