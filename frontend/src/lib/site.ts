import type { Locale } from "@/api/contract";

export function isLocale(value: string): value is Locale {
  return value === "ar" || value === "en";
}

export function servicePath(locale: Locale, id: string) {
  return `/${locale}/services/${encodeURIComponent(id)}`;
}

export function alternatePath(pathname: string, locale: Locale) {
  const segments = pathname.split("/");
  segments[1] = locale === "ar" ? "en" : "ar";
  return segments.join("/");
}

export function siteOrigin() {
  try {
    const url = new URL(process.env.BARDI_SITE_ORIGIN || "http://localhost:3000");
    if ((url.protocol === "http:" || url.protocol === "https:") && !url.username && !url.password) return url.origin;
  } catch { /* Configuration is never exposed in errors or HTML. */ }
  return "http://localhost:3000";
}

export function pageAlternates(path: string, locale: Locale) {
  return { canonical: `/${locale}${path}`, languages: { ar: `/ar${path}`, en: `/en${path}`, "x-default": `/ar${path}` } };
}

const en = {
  brand: "Bardi",
  title: "Prepare your paperwork, one question at a time.",
  description: "An independent guide to preparing Egyptian paperwork. Answer questions about your situation to find relevant documents, steps, and things to verify.",
  intro: "Tell us a little about your situation. We’ll help you understand what to prepare, what to do, and what still needs checking.",
  services: "What are you preparing for?",
  servicesHint: "Choose from the services currently available in Bardi.",
  allServices: "All services",
  guidance: "Useful guidance. Clear limits.",
  guidanceBody: "Official requirements and practical preparation are clearly labelled. Sources and verification dates stay alongside the guidance.",
  guidanceLimits: "If something is uncertain, we’ll say so—not guess. Bardi is a preparation guide, not a decision about your application.",
  independent: "An independent guide. Not a government service.",
  privacy: "Privacy and your answers",
  skip: "Skip to content",
  noServices: "No services are available yet",
  noServicesHint: "Bardi isn’t listing any services right now. Please check again later.",
  unavailable: "We couldn’t load the services",
  unavailableHint: "The service directory is temporarily unavailable. Try loading it again in a moment.",
  retry: "Load services again",
  start: "Start the questions",
  before: "Before you start",
  beforeIntro: "We’ll ask about your situation and use your answers to prepare relevant guidance. The questions depend on your answers; there’s no fixed number of steps.",
  preparation: "What you can expect",
  expect: "A preparation checklist, relevant steps, fee information where verified, and guidance on where to apply where supported. Some parts may still need checking.",
  noApplication: "This does not submit an application or book an appointment. Check the guidance with the responsible authority before acting.",
  tab: "No account. Answers stay in this tab.",
  tabHint: "Submitted answers are sent to Bardi to prepare guidance, not to save a case on the server. Browsers may restore tabs; clear your answers before leaving a shared device.",
  beginHint: "You can review answers, change them, or clear them at any point.",
  questions: "Your questions and guidance",
  javascript: "The questionnaire needs JavaScript. Enable it in your browser to answer questions and prepare guidance.",
  back: "Back to the service",
  loading: "Loading…",
  missing: "We couldn’t find this page",
  missingHint: "This service may no longer be available, or the address may be incorrect. Go back to the available services to continue.",
  error: "This page couldn’t open",
  errorHint: "Try opening it again. If you were answering questions, submitted answers may still be in this tab’s storage.",
  tryAgain: "Try opening the page again",
};
type Copy = { [K in keyof typeof en]: string };
const ar: Copy = {
  brand: "بردي",
  title: "جهّز ورقك، سؤال بسؤال.",
  description: "دليل مستقل يساعدك تجهّز ورقك في مصر. جاوب على أسئلة عن وضعك عشان تعرف الأوراق والخطوات المناسبة، وإيه اللي لسه محتاج تتأكد منه.",
  intro: "احكيلنا شوية عن وضعك. هنساعدك تعرف تجهّز إيه، تعمل إيه، وإيه اللي لسه محتاج تتأكد منه.",
  services: "بتجهّز لإيه؟",
  servicesHint: "اختار من الخدمات المتاحة في بردي دلوقتي.",
  allServices: "كل الخدمات",
  guidance: "إرشادات مفيدة، وحدود واضحة.",
  guidanceBody: "هنفرّق لك بين المتطلبات الرسمية والتجهيزات العملية. ومصادر المعلومات وتواريخ التحقق هتفضل جنب الإرشادات.",
  guidanceLimits: "لو حاجة مش مؤكدة، هنقولك من غير تخمين. بردي دليل يساعدك تجهّز، مش قرار بخصوص طلبك.",
  independent: "دليل مستقل، مش خدمة حكومية.",
  privacy: "خصوصيتك وإجاباتك",
  skip: "روح للمحتوى",
  noServices: "مفيش خدمات متاحة حاليًا",
  noServicesHint: "مفيش خدمات نقدر نعرضها دلوقتي. ارجع تاني بعد شوية.",
  unavailable: "ما قدرناش نحمّل الخدمات",
  unavailableHint: "قائمة الخدمات مش متاحة مؤقتًا. جرّب تحمّلها تاني بعد شوية.",
  retry: "حمّل الخدمات تاني",
  start: "ابدأ الأسئلة",
  before: "قبل ما تبدأ",
  beforeIntro: "هنسألك عن وضعك، ونستخدم إجاباتك عشان نجهّز إرشادات مناسبة. الأسئلة بتعتمد على إجاباتك؛ مفيش عدد خطوات ثابت.",
  preparation: "إيه اللي ممكن تلاقيه؟",
  expect: "قائمة تجهيزات، وخطوات مناسبة، ومعلومات عن الرسوم لو متحقق منها، وجهات التقديم اللي عندنا معلومات تدعمها. ممكن بعض التفاصيل تفضل محتاجة تأكيد.",
  noApplication: "ده مش تقديم طلب ولا حجز ميعاد. راجع الإرشادات مع الجهة المختصة قبل ما تتحرك.",
  tab: "من غير حساب. إجاباتك في التبويب ده.",
  tabHint: "إجاباتك بتتبعت لبردي عشان نجهّز الإرشادات، مش عشان نحفظ حالة على الخادم. المتصفح ممكن يرجّع التبويبات؛ امسح إجاباتك قبل ما تسيب جهاز مشترك.",
  beginHint: "تقدر تراجع إجاباتك، تغيّرها، أو تمسحها في أي وقت.",
  questions: "أسئلتك وإرشاداتك",
  javascript: "الأسئلة محتاجة JavaScript. فعّله في متصفحك عشان تقدر تجاوب وتجهّز الإرشادات.",
  back: "ارجع للخدمة",
  loading: "بنحمّل الصفحة…",
  missing: "ما لقيناش الصفحة دي",
  missingHint: "الخدمة ممكن تكون مش متاحة دلوقتي، أو العنوان مش صحيح. ارجع للخدمات المتاحة عشان تكمّل.",
  error: "ما قدرناش نفتح الصفحة",
  errorHint: "جرّب تفتحها تاني. لو كنت بتجاوب على الأسئلة، إجاباتك اللي بعتها ممكن تكون لسه في تخزين التبويب ده.",
  tryAgain: "جرّب تفتح الصفحة تاني",
};
export function siteCopy(locale: Locale): Copy { return locale === "ar" ? ar : en; }
