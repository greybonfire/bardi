import type { Locale } from "@/api/contract";

type Label = readonly [ar: string, en: string];

// Presentation only, from backend/planning/facts.py and the three production
// knowledge/importers. These labels do not select Questions or imply eligibility.
// Unknown future keys/options remain verbatim rather than becoming a closest match.
export const fieldLabels: Record<string, Label> = {
  citizenship: ["الجنسية", "Citizenship"],
  application_location: ["مكان تقديم الطلب", "Application location"],
  existing_passport_state: ["حالة جواز السفر الحالي", "Current passport status"],
  passport_class: ["فئة جواز السفر", "Passport class"],
  birth_date: ["تاريخ الميلاد", "Date of birth"],
  sex: ["الجنس المثبت في المستندات", "Sex on official documents"],
  national_id_status: ["صلاحية بطاقة الرقم القومي وبياناتها", "National ID validity and data"],
  is_student: ["القيد الدراسي الحالي", "Current student status"],
  has_current_enrollment_certificate: ["شهادة القيد الدراسي الحالية", "Current enrollment certificate"],
  has_military_status_document: ["مستند الموقف التجنيدي", "Military-status document"],
  has_required_photos: ["الصور المطلوبة", "Required photos"],
  service_level: ["مستوى الخدمة", "Service level"],
  residence_police_jurisdiction: ["قسم أو مركز شرطة محل الإقامة", "Residence police district or centre"],
  minor_presenting_adult_role: ["صفة الشخص المرافق للقاصر", "Adult accompanying the minor"],
  national_id_possession_state: ["حالة بطاقة الرقم القومي الحالية", "Current National ID status"],
  national_id_expiry_date: ["تاريخ انتهاء بطاقة الرقم القومي", "National ID expiry date"],
  national_id_data_change_kind: ["البيانات المطلوب تغييرها", "Data to change"],
  residence_governorate: ["محافظة محل الإقامة", "Governorate of residence"],
  residence_district: ["مركز أو قسم محل الإقامة", "Residence district or centre"],
  father_alive: ["الوالد على قيد الحياة", "Father is alive"],
  other_living_sons_of_father_count: ["عدد الأبناء الذكور الآخرين الأحياء للوالد", "Father’s other living sons"],
  father_unable_to_earn_status: ["حالة إثبات عدم قدرة الوالد على الكسب", "Documented father’s inability to earn"],
  other_capable_family_support_for_father: ["وجود عائل آخر قادر للوالد", "Other capable support for father"],
  mother_family_status: ["الحالة العائلية للوالدة", "Mother’s family status"],
  other_capable_family_support_for_mother: ["وجود عائل آخر قادر للوالدة", "Other capable support for mother"],
  unmarried_sisters_requiring_support_count: ["عدد الأخوات غير المتزوجات المعنيات بالطلب", "Unmarried sisters relevant to the request"],
  other_capable_family_support_for_sisters: ["وجود عائل آخر قادر للأخوات", "Other capable support for sisters"],
  missing_relative_category: ["صفة القريب المفقود المسجلة", "Recorded missing-relative category"],
  missing_relative_cause: ["سبب الفقد المسجل", "Recorded cause of disappearance"],
  missing_relative_alive_status: ["الحالة الحالية للقريب المفقود", "Current missing-relative status"],
  applicant_largest_eligible_relative_status: ["إثبات صفة القريب الأكبر المستوفي للوصف", "Documented largest eligible relative status"],
  sibling_service_status: ["حالة خدمة الأخ", "Brother’s service status"],
  applicant_eldest_remaining_brother_status: ["إثبات ترتيب الأخ الأكبر المتبقي", "Documented eldest remaining brother status"],
  article7_third_exclusion_status: ["استبعادات المادة ٧/ثالثاً", "Article 7/Third exclusions"],
};

const documented: Record<string, Label> = {
  authority_documented_yes: ["نعم، مثبت لدى الجهة المختصة", "Yes, recorded by the authority"],
  authority_documented_no: ["لا، مثبت لدى الجهة المختصة", "No, recorded by the authority"],
};
const support: Record<string, Label> = {
  none_known: ["لا يوجد عائل آخر معروف", "No other known support"],
  present: ["يوجد عائل آخر قادر", "Other capable support is present"],
  unknown: ["غير معروف", "Unknown"],
};
export const enumLabels: Record<string, Record<string, Label>> = {
  citizenship: { egyptian: ["مصري", "Egyptian"], other: ["جنسية أخرى", "Other citizenship"] },
  application_location: { inside_egypt: ["داخل مصر", "Inside Egypt"], outside_egypt: ["خارج مصر", "Outside Egypt"] },
  existing_passport_state: {
    expired: ["منتهي الصلاحية", "Expired"], pages_full: ["الصفحات ممتلئة", "Pages full"],
    valid_with_pages: ["ساري وفيه صفحات متاحة", "Valid, with available pages"], lost: ["مفقود", "Lost"],
    damaged: ["تالف", "Damaged"], none: ["ما عنديش جواز سفر", "No passport"],
  },
  passport_class: { ordinary: ["جواز عادي", "Ordinary passport"], other: ["فئة أخرى", "Another class"] },
  sex: { male: ["ذكر", "Male"], female: ["أنثى", "Female"] },
  national_id_status: {
    valid_current_data: ["سارية وبياناتها محدثة", "Valid, with current data"],
    invalid_or_expired: ["غير سارية أو منتهية", "Invalid or expired"], not_held: ["ما عنديش بطاقة", "No card held"],
  },
  service_level: { standard: ["عادية", "Standard"], urgent: ["عاجلة — يوم العمل التالي", "Urgent — next working day"], premium: ["مميزة — نفس اليوم", "Premium — same day"] },
  minor_presenting_adult_role: { parent: ["أب أو أم", "Parent"], legal_guardian: ["ولي أو وصي قانوني", "Legal guardian"], other: ["صفة أخرى", "Other"], unknown: ["غير معروف", "Unknown"] },
  national_id_possession_state: { held: ["البطاقة موجودة معايا", "Card held"], lost: ["مفقودة", "Lost"], damaged: ["تالفة", "Damaged"], none: ["ما عنديش بطاقة", "No card"] },
  national_id_data_change_kind: {
    none: ["مفيش بيانات محتاجة تغيير", "No data changes"], residence: ["محل الإقامة", "Residence"],
    profession: ["المهنة", "Profession"], marital_status: ["الحالة الاجتماعية", "Marital status"],
    other: ["بيانات أخرى", "Other data"], multiple: ["أكثر من نوع بيانات", "Multiple data types"],
  },
  father_unable_to_earn_status: {
    authority_documented_unable: ["عدم القدرة على الكسب مثبت لدى الجهة المختصة", "Inability to earn is documented by the authority"],
    not_documented_unable: ["عدم القدرة على الكسب غير مثبت", "Inability to earn is not documented"],
  },
  other_capable_family_support_for_father: support,
  other_capable_family_support_for_mother: support,
  other_capable_family_support_for_sisters: support,
  mother_family_status: {
    widowed: ["أرملة", "Widowed"], irrevocably_divorced: ["مطلقة طلاقًا بائنًا", "Irrevocably divorced"],
    husband_authority_documented_unable: ["زوجها مثبت عدم قدرته على الكسب لدى الجهة المختصة", "Husband’s inability to earn is documented by the authority"],
    other: ["حالة أخرى", "Other status"],
  },
  missing_relative_category: { officer: ["ضابط", "Officer"], volunteer: ["متطوع", "Volunteer"], conscript: ["مجند", "Conscript"], citizen: ["مواطن", "Citizen"], none: ["لا يوجد قريب مفقود", "No missing relative"] },
  missing_relative_cause: { war_operations: ["عمليات حربية", "War operations"], terrorist_operations: ["عمليات إرهابية", "Terrorist operations"], other: ["سبب آخر", "Other cause"] },
  missing_relative_alive_status: { missing: ["ما زال مفقودًا", "Still missing"], returned_or_proven_alive: ["عاد أو ثبت أنه على قيد الحياة", "Returned or proven alive"], unknown: ["غير معروف", "Unknown"] },
  applicant_largest_eligible_relative_status: documented,
  sibling_service_status: { compulsory_service: ["في الخدمة الإلزامية", "In compulsory service"], reserve_recall: ["مستدعى للاحتياط", "Called for reserve service"], none: ["لا تنطبق أي من الحالتين", "Neither applies"] },
  applicant_eldest_remaining_brother_status: documented,
  article7_third_exclusion_status: { none_documented: ["لا يوجد استبعاد مثبت", "No documented exclusion"], exclusion_present: ["يوجد استبعاد", "An exclusion is present"], unknown: ["غير معروف", "Unknown"] },
};

function localized(label: Label, locale: Locale): string { return label[locale === "ar" ? 0 : 1]; }
export function fieldLabel(key: string, locale: Locale): string {
  return Object.hasOwn(fieldLabels, key) ? localized(fieldLabels[key], locale) : key;
}
export function answerLabel(key: string, value: string | boolean | number, locale: Locale): string {
  if (typeof value === "boolean") return locale === "ar" ? (value ? "أيوه" : "لأ") : (value ? "Yes" : "No");
  if (typeof value === "number") return new Intl.NumberFormat(locale, { useGrouping: false }).format(value);
  const options = Object.hasOwn(enumLabels, key) ? enumLabels[key] : undefined;
  return options && Object.hasOwn(options, value) ? localized(options[value], locale) : value;
}
