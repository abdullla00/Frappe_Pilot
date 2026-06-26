# Pilot UI and chip catalogs — English + Kurdish Sorani (ckb) + Arabic (ar)

import re

import frappe

LOCALE_CODES = frozenset({"en", "ckb", "ar"})
PILOT_CHIP_LOCALES = ("ckb", "ar")

RTL_LOCALE_CODES = frozenset({"ckb", "ar", "fa", "ur", "he"})

PILOT_LOCALE_LABELS = {
	"en": "EN",
	"ckb": "کوردی",
	"ar": "العربية",
}

# Legacy Select value migration only
LANGUAGE_LABEL_TO_CODE = {
	"Kurdish Sorani": "ckb",
}


def pilot_locale_label(code, language_name=None):
	if code in PILOT_LOCALE_LABELS:
		return PILOT_LOCALE_LABELS[code]
	if language_name:
		return language_name[:12]
	return (code or "en").upper()

KURDISH_SORANI_ALIASES = (
	"kurdish",
	"kurdish sorani",
	"sorani",
	"central kurdish",
	"کوردی",
	"سۆرانی",
	"سورانی",
)

DIAGNOSE_PROMPTS = frozenset({
	"Diagnose this record",
	"Flag anything unusual",
	"Why are these records here?",
	"Why is this total high?",
	"Diagnose rental status",
	"Diagnose posting issues",
	"Check Job Order linkage",
})

UI_STRINGS = {
	"en": {
		"trigger_label": "Pilot",
		"trigger_title": "Open Frappe Pilot",
		"trigger_close_label": "Close Frappe Pilot",
		"trigger_close_short": "Close",
		"panel_title": "Frappe Pilot",
		"tab_advisor": "Advisor",
		"tab_insight": "Insight",
		"tab_build": "Build",
		"subtab_build_chat": "Chat",
		"subtab_changes": "Changes",
		"placeholder_advisor": "Ask about this page or where to go…",
		"placeholder_build": "Describe a field, DocType, or automation…",
		"placeholder_advisor_form": "Summarize or ask about {label}…",
		"placeholder_advisor_form_new": "What should I enter on this {doctype}?…",
		"placeholder_advisor_list": "Ask about this {doctype} list…",
		"placeholder_advisor_report": "Explain or question this {report} report…",
		"placeholder_advisor_page": "Ask about this page or where to go…",
		"placeholder_build_form": "Add a field, script, or workflow for {doctype}…",
		"placeholder_build_list": "Build something for {doctype}…",
		"placeholder_build_page": "Describe a field, DocType, or automation…",
		"placeholder_insight": "Ask about business performance, reports, or KPIs…",
		"settings_gear_title": "Pilot Settings",
		"setup_title": "Pilot isn't connected yet",
		"setup_desc": "Add an API key to unlock AI advisor, guided help, and build tools inside ERPNext.",
		"setup_cta": "Configure API Keys",
		"setup_secondary_sm": "Or set keys in site_config.json for server deployments.",
		"setup_secondary_user": "Contact your System Manager to configure Pilot and add an API key.",
		"typing_advisor": "Analyzing…",
		"typing_insight": "Generating insight…",
		"typing_build": "Thinking…",
		"nav_go_to": "Go to {label}",
		"nav_open": "Open {label}",
		"locale_en": "EN",
		"locale_ckb": "کوردی",
		"locale_ar": "العربية",
		"position_right": "Dock right",
		"position_left": "Dock left",
		"position_bottom": "Dock bottom",
		"position_reset_default": "Reset to site default",
		"insight_save_snapshot": "Save snapshot",
		"insight_open_report": "Open report",
		"insight_copy_table": "Copy table",
		"insight_new_conversation": "New conversation",
		"insight_evidence": "Based on: {sources}",
		"insight_partial_results": "Partial results",
		"insight_sections_count": "{count} sections",
		"insight_sql_denied": "Read-only SQL is not available",
		"insight_doctype_excluded": "This DocType is excluded from Insight",
		"advisor_new_conversation": "Clear conversation",
		"advisor_chip_group_record": "This record",
		"advisor_chip_group_howto": "How to",
		"advisor_card_item": "Item",
		"advisor_card_calculation": "Calculation",
		"advisor_card_amount": "Amount",
		"advisor_card_assumptions": "Assumptions",
		"advisor_card_findings": "Findings",
		"advisor_card_evidence": "Evidence",
		"advisor_card_verify": "What to verify",
		"advisor_card_copy": "Copy breakdown",
	},
	"ckb": {
		"trigger_label": "پایلۆت",
		"trigger_title": "کردنەوەی Frappe Pilot",
		"trigger_close_label": "داخستنی Frappe Pilot",
		"trigger_close_short": "داخستن",
		"panel_title": "Frappe Pilot",
		"tab_advisor": "ڕاوێژکار",
		"tab_insight": "تێڕوانین",
		"tab_build": "دروستکردن",
		"subtab_build_chat": "گفتوگۆ",
		"subtab_changes": "گۆڕانکاری",
		"placeholder_advisor": "لەبارەی ئەم پەڕە بپرسە یان بڵێ بچم بۆ کوێ…",
		"placeholder_build": "خانە، DocType یان ئۆتۆمەیشن وەسف بکە…",
		"placeholder_advisor_form": "پوختە بکە یان لەبارەی {label} بپرسە…",
		"placeholder_advisor_form_new": "چی پێویستە لەم {doctype} بنووسم؟…",
		"placeholder_advisor_list": "لەبارەی لیستی {doctype} بپرسە…",
		"placeholder_advisor_report": "ڕاپۆرتی {report} شەرح بکە یان پرسیار بکە…",
		"placeholder_advisor_page": "لەبارەی ئەم پەڕە بپرسە یان بڵێ بچم بۆ کوێ…",
		"placeholder_build_form": "خانە، سکریپت یان workflow بۆ {doctype} زیاد بکە…",
		"placeholder_build_list": "شتێک بۆ {doctype} دروست بکە…",
		"placeholder_build_page": "خانە، DocType یان ئۆتۆمەیشن وەسف بکە…",
		"placeholder_insight": "لەبارەی کارکردی بازرگانی، ڕاپۆرت یان KPI بپرسە…",
		"settings_gear_title": "ڕێکخستنی پایلۆت",
		"setup_title": "پایلۆت هێشتا پەیوەندی نییە",
		"setup_desc": "کلیلی API زیاد بکە بۆ ڕاوێژکار، ڕێنمایی و دروستکردن لە ERPNext.",
		"setup_cta": "ڕێکخستنی کلیلەکانی API",
		"setup_secondary_sm": "یان کلیل لە site_config.json دابنێ بۆ ڕاژە.",
		"setup_secondary_user": "پەیوەندی بە بەڕێوەبەرەکەت بکە بۆ ڕێکخستنی پایلۆت.",
		"typing_advisor": "شیکردنەوە…",
		"typing_insight": "دروستکردنی تێڕوانین…",
		"typing_build": "بیرکردنەوە…",
		"nav_go_to": "بڕۆ بۆ {label}",
		"nav_open": "بکەرەوە {label}",
		"locale_en": "EN",
		"locale_ckb": "کوردی",
		"locale_ar": "العربية",
		"position_right": "لای ڕاست",
		"position_left": "لای چەپ",
		"position_bottom": "لە خوارەوە",
		"position_reset_default": "گەڕانەوە بۆ بنەڕەتی ماڵپەڕ",
		"insight_save_snapshot": "پاشەکەوتکردنی وێنە",
		"insight_open_report": "کردنەوەی ڕاپۆرت",
		"insight_copy_table": "لەبەرگرتنەوەی خشتە",
		"insight_new_conversation": "گفتوگۆی نوێ",
		"insight_evidence": "لەسەر بنەمای: {sources}",
		"insight_partial_results": "ئەنجامی بەشێکی",
		"insight_sections_count": "{count} بەش",
		"insight_sql_denied": "SQL تەنها بۆ خوێندنەوە بەردەست نییە",
		"insight_doctype_excluded": "ئەم DocType لە تێڕوانیندا قەدەغەیە",
		"advisor_new_conversation": "گفتوگۆ بسڕەوە",
		"advisor_chip_group_record": "ئەم تۆمارە",
		"advisor_chip_group_howto": "چۆن",
		"advisor_card_item": "کاڵا",
		"advisor_card_calculation": "ژماردن",
		"advisor_card_amount": "بڕ",
		"advisor_card_assumptions": "گریمانەکان",
		"advisor_card_findings": "دۆزینەوەکان",
		"advisor_card_evidence": "بەڵگە",
		"advisor_card_verify": "چی بپشکنیت",
		"advisor_card_copy": "کۆپیکردنیوردەکاری",
	},
	"ar": {
		"trigger_label": "الطيار",
		"trigger_title": "فتح Frappe Pilot",
		"trigger_close_label": "إغلاق Frappe Pilot",
		"trigger_close_short": "إغلاق",
		"panel_title": "Frappe Pilot",
		"tab_advisor": "المستشار",
		"tab_insight": "رؤى",
		"tab_build": "البناء",
		"subtab_build_chat": "محادثة",
		"subtab_changes": "التغييرات",
		"placeholder_advisor": "اسأل عن هذه الصفحة أو إلى أين تذهب…",
		"placeholder_build": "صف حقلًا أو نوع مستند أو أتمتة…",
		"placeholder_advisor_form": "لخّص أو اسأل عن {label}…",
		"placeholder_advisor_form_new": "ماذا أدخل في {doctype}؟…",
		"placeholder_advisor_list": "اسأل عن قائمة {doctype}…",
		"placeholder_advisor_report": "اشرح أو اسأل عن تقرير {report}…",
		"placeholder_advisor_page": "اسأل عن هذه الصفحة أو إلى أين تذهب…",
		"placeholder_build_form": "أضف حقلًا أو سكربتًا أو سير عمل لـ {doctype}…",
		"placeholder_build_list": "ابنِ شيئًا لـ {doctype}…",
		"placeholder_build_page": "صف حقلًا أو نوع مستند أو أتمتة…",
		"placeholder_insight": "اسأل عن أداء الأعمال أو التقارير أو مؤشرات الأداء…",
		"settings_gear_title": "إعدادات الطيار",
		"setup_title": "الطيار غير متصل بعد",
		"setup_desc": "أضف مفتاح API لتفعيل المستشار والإرشاد وأدوات البناء داخل ERPNext.",
		"setup_cta": "تهيئة مفاتيح API",
		"setup_secondary_sm": "أو ضع المفاتيح في site_config.json للنشر على الخادم.",
		"setup_secondary_user": "تواصل مع مدير النظام لتهيئة الطيار وإضافة مفتاح API.",
		"typing_advisor": "جارٍ التحليل…",
		"typing_insight": "جارٍ إنشاء الرؤى…",
		"typing_build": "جارٍ التفكير…",
		"nav_go_to": "انتقل إلى {label}",
		"nav_open": "افتح {label}",
		"locale_en": "EN",
		"locale_ckb": "کوردی",
		"locale_ar": "العربية",
		"position_right": "إرساء يمين",
		"position_left": "إرساء يسار",
		"position_bottom": "إرساء أسفل",
		"position_reset_default": "إعادة تعيين الافتراضي للموقع",
		"insight_save_snapshot": "حفظ اللقطة",
		"insight_open_report": "فتح التقرير",
		"insight_copy_table": "نسخ الجدول",
		"insight_new_conversation": "محادثة جديدة",
		"insight_evidence": "بناءً على: {sources}",
		"insight_partial_results": "نتائج جزئية",
		"insight_sections_count": "{count} أقسام",
		"insight_sql_denied": "SQL للقراءة فقط غير متاح",
		"insight_doctype_excluded": "نوع المستند هذا مستبعد من الرؤى",
		"advisor_new_conversation": "مسح المحادثة",
		"advisor_chip_group_record": "هذا السجل",
		"advisor_chip_group_howto": "كيف",
		"advisor_card_item": "الصنف",
		"advisor_card_calculation": "الحساب",
		"advisor_card_amount": "المبلغ",
		"advisor_card_assumptions": "الافتراضات",
		"advisor_card_findings": "النتائج",
		"advisor_card_evidence": "الدليل",
		"advisor_card_verify": "ما يجب التحقق منه",
		"advisor_card_copy": "نسخ التفاصيل",
	},
}

SPLIT_CHIP_PAIRS = 2

# Canonical English prompt -> Kurdish Sorani display subtitle
CHIP_TRANSLATIONS_CKB = {
	# Analyze — generic
	"Summarize this record": "پوختەی ئەم تۆمارە",
	"Diagnose this record": "دەستنیشانکردنی کێشەکان",
	"What should I do next?": "دەبێت چی بکەم؟",
	"Flag anything unusual": "هەر شتێکی نائاسایی نیشان بدە",
	"What fields are required?": "چ خانەیەک پێویستە؟",
	"What is this form for?": "ئەم فۆرمە بۆ چییە؟",
	"Walk me through filling this in": "ڕێنمایی پڕکردنەوەم بدە",
	"Pre-submit checklist": "پێرستی پێش ناردن",
	"Can I submit this?": "دەتوانم بنێرم؟",
	"What to fix before submit?": "پێش ناردن چی چاک بکەم؟",
	"Summarize draft": "پوختەی ڕەشنووس",
	"Summarize this quotation": "پوختەی ئەم نرخنامەیە",
	"Calculate for 4 days": "ژماردن بۆ ٤ ڕۆژ",
	"Calculate for 7 days": "ژماردن بۆ ٧ ڕۆژ",
	"Calculate for 14 days": "ژماردن بۆ ١٤ ڕۆژ",
	"Convert to Sales Order": "گۆڕین بۆ داواکاری فرۆشتن",
	"Summarize this job": "پوختەی ئەم کارە",
	"Linked tickets?": "تکتە پەیوەندیدارەکان؟",
	"Explain days charged": "ڕوونکردنەوەی ڕۆژە ژماردراوەکان",
	"Summarize this ticket": "پوختەی ئەم تکتە",
	"Linked Job Order?": "فەرمانی کاری پەیوەندیدار؟",
	"Summarize this rental order": "پوختەی داواکاری کرێ",
	"Summarize this delivery": "پوختەی گەیاندن",
	"Summarize this return": "پوختەی گەڕاندنەوە",
	"Summarize this inspection": "پوختەی پشکنین",
	"What is this quotation for?": "ئەم نرخنامەیە بۆ چییە؟",
	"How do rental lines work?": "هێڵەکانی کرێ چۆن کاردەکەن؟",
	"Summarize current settings": "پوختەی ڕێکخستنەکان",
	"Check payment status": "دۆخی پارەدان بپشکنە",
	"Verify GL entries": "تۆمارە گشتییەکان بپشکنە",
	"Check unallocated amount": "بڕی نەدابەشکراو بپشکنە",
	"Check fulfillment status": "دۆخی جێبەجێکردن بپشکنە",
	"Check Job Order linkage": "پەیوەندی فەرمانی کار بپشکنە",
	"Diagnose rental status": "دۆخی کرێ بپشکنە",
	"Check Rental Order link": "پەیوەندی داواکاری کرێ بپشکنە",
	"Summarize this customer": "پوختەی ئەم کڕیارە",
	"Check outstanding balance": "باڵانسی ماوە بپشکنە",
	"Summarize this item": "پوختەی ئەم کاڵایە",
	"Check stock levels": "ئاستی کۆگا بپشکنە",
	"Why are these records here?": "بۆچی ئەم تۆمارانە لێرەن؟",
	"What do the columns mean?": "ستوونەکان چی دەگەیەنن؟",
	"What can I do on this list?": "لەم لیستەدا چی دەتوانم بکەم؟",
	"Why are these invoices here?": "بۆچی ئەم پسوڵانە لێرەن؟",
	"Show unpaid invoices": "پسوڵە نەدراوەکان پیشان بدە",
	"Why are these customers here?": "بۆچی ئەم کڕیارانە لێرەن؟",
	"What does this report show?": "ئەم ڕاپۆرتە چی پیشان دەدات؟",
	"Why is this total high?": "بۆچی کۆی گشتی بەرزە؟",
	"Explain the filters": "فلتەرەکان ڕوون بکەرەوە",
	"Explain this balance": "ئەم باڵانسە ڕوون بکەرەوە",
	"Who owes the most?": "کێ زۆرتر قەرزدارە؟",
	"What do we owe?": "چەند قەرزمان هەیە؟",
	"Which items are low?": "کام کاڵاکان کەمن؟",
	"What is this page for?": "ئەم پەڕەیە بۆ چییە؟",
	"What can I do here?": "لێرە چی دەتوانم بکەم؟",
	"What page am I on?": "لە کام پەڕەدام؟",
	"Where should I go to analyze a document?": "بۆ شیکردنەوە بچم بۆ کوێ؟",
	"Navigate to a document to analyze it": "بچۆ بۆ تۆمارێک بۆ شیکردنەوە",
	"What can I analyze on this page?": "لەم پەڕەیەدا چی دەتوانم شیکار بکەم؟",
	"Summarize selling activity": "پوختەی فرۆشتن",
	"Summarize buying activity": "پوختەی کڕین",
	"Check stock implications": "کاریگەری کۆگا بپشکنە",
	"Check accounting impact": "کاریگەری ژمێریاری بپشکنە",
	"What should I check?": "چی بپشکنم؟",
	# Pilot Settings
	"Explain each settings tab": "هەر تابێکی ڕێکخستن ڕوون بکەرەوە",
	"How do API keys work here?": "کلیلەکانی API لێرە چۆن کاردەکەن؟",
	"What should I configure first?": "سەرەتا چی ڕێکبخەم؟",
	"What is Pilot Settings for?": "ڕێکخستنی پایلۆت بۆ چییە؟",
	# Guide — general
	"What is a DocType?": "DocType چییە؟",
	"How do I add a custom field?": "چۆن خانەی تایبەت زیاد بکەم؟",
	"How do workflows work?": "کارپێکردنەکان چۆن کاردەکەن؟",
	"How do I set up permissions?": "چۆن مۆڵەت دابنێم؟",
	# Guide — Customer
	"How do I add a GSTIN field?": "چۆن خانەی GSTIN زیاد بکەم؟",
	"How do I set a credit limit?": "چۆن سنووری قەرز دابنێم؟",
	"How do I link contacts?": "چۆن پەیوەندی زیاد بکەم؟",
	"How do I create a Sales Order?": "چۆن داواکاری فرۆشتن دروست بکەم؟",
	"What happens when I submit this?": "کاتێک دەینێرم چی ڕوودەدات؟",
	"How do I apply a discount?": "چۆن داشکاندن جێبەجێ بکەم؟",
	"How do I create a credit note?": "چۆن تۆماری قەرز دروست بکەم؟",
	"How do I record a partial payment?": "چۆن پارەدانی بەشێکی تۆمار بکەم؟",
	"How do I create a new customer?": "چۆن کڕیاری نوێ دروست بکەم؟",
	"How do I filter by territory?": "چۆن بە ناوچە فلتەر بکەم؟",
	"How do I export this list?": "چۆن ئەم لیستە هەناردە بکەم؟",
	"How do I bulk update?": "چۆن نوێکردنەوەی کۆمەڵ بکەم؟",
	"How do I create a new invoice?": "چۆن پسوڵەی نوێ دروست بکەم؟",
	"How do I filter unpaid invoices?": "چۆن پسوڵە نەدراوەکان فلتەر بکەم؟",
	"How do I see overdue invoices?": "چۆن پسوڵە دواکەوتووەکان ببینم؟",
	"How do I do a stock transfer?": "چۆن گواستنەوەی کۆگا بکەم؟",
	"How do I check stock levels?": "چۆن ئاستی کۆگا بپشکنم؟",
	"What is a Stock Entry?": "تۆماری کۆگا چییە؟",
	"How do I set a reorder level?": "چۆن ئاستی دووبارە داواکاری دابنێم؟",
	"How do I reconcile a bank statement?": "چۆن ڕێکخستنی بانک بکەم؟",
	"How do I create a Journal Entry?": "چۆن تۆماری ڕۆژانە دروست بکەم؟",
	"How do I record a payment?": "چۆن پارەدان تۆمار بکەم؟",
	"How do I view the general ledger?": "چۆن تۆماری گشتی ببینم؟",
	"How do I filter this report?": "چۆن ئەم ڕاپۆرتە فلتەر بکەم؟",
	"How do I export report data?": "چۆن داتای ڕاپۆرت هەناردە بکەم؟",
}

BUILD_LABEL_CK = {
	"Custom Field": "خانەی تایبەت",
	"Custom Fields": "خانەی تایبەت",
	"Server Script": "سکریپتی سێرڤەر",
	"Client Script": "سکریپتی کڕیار",
	"Workflow": "کارپێکردن",
	"Workflows": "کارپێکردن",
	"New DocType": "DocType نوێ",
	"Scripts": "سکریپت",
	"Reorder Level": "ئاستی دووبارە داواکاری",
	"Stock Script": "سکریپتی کۆگا",
	"Payment Script": "سکریپتی پارەدان",
}

BUILD_LABEL_AR = {
	"Custom Field": "حقل مخصص",
	"Custom Fields": "حقل مخصص",
	"Server Script": "سكربت الخادم",
	"Client Script": "سكربت العميل",
	"Workflow": "سير عمل",
	"Workflows": "سير عمل",
	"New DocType": "نوع مستند جديد",
	"Scripts": "سكربتات",
	"Reorder Level": "حد إعادة الطلب",
	"Stock Script": "سكربت المخزون",
	"Payment Script": "سكربت الدفع",
}

# Canonical English prompt -> Arabic display subtitle
CHIP_TRANSLATIONS_AR = {
	"Summarize this record": "لخّص هذا السجل",
	"Diagnose this record": "شخّص هذا السجل",
	"What should I do next?": "ماذا أفعل بعد ذلك؟",
	"Flag anything unusual": "أبرز أي شيء غير عادي",
	"What fields are required?": "ما الحقول المطلوبة؟",
	"What is this form for?": "ما غرض هذا النموذج؟",
	"Walk me through filling this in": "أرشدني لملء هذا النموذج",
	"Pre-submit checklist": "قائمة قبل الإرسال",
	"Can I submit this?": "هل يمكنني الإرسال؟",
	"What to fix before submit?": "ماذا أصلح قبل الإرسال؟",
	"Summarize draft": "لخّص المسودة",
	"Summarize this order": "لخّص هذا الطلب",
	"Summarize this quotation": "لخّص عرض السعر",
	"Calculate for 4 days": "احسب لـ 4 أيام",
	"Calculate for 7 days": "احسب لـ 7 أيام",
	"Calculate for 14 days": "احسب لـ 14 يوماً",
	"Convert to Sales Order": "تحويل إلى أمر بيع",
	"Summarize this job": "لخّص أمر العمل",
	"Linked tickets?": "التذاكر المرتبطة؟",
	"Explain days charged": "اشرح الأيام المحتسبة",
	"Summarize this ticket": "لخّص هذه التذكرة",
	"Linked Job Order?": "أمر العمل المرتبط؟",
	"Summarize this rental order": "لخّص أمر الإيجار",
	"Summarize this delivery": "لخّص التسليم",
	"Summarize this return": "لخّص الإرجاع",
	"Summarize this inspection": "لخّص الفحص",
	"What is this quotation for?": "ما غرض عرض السعر؟",
	"How do rental lines work?": "كيف تعمل بنود الإيجار؟",
	"Summarize current settings": "لخّص الإعدادات الحالية",
	"Check payment status": "تحقق من حالة الدفع",
	"Verify GL entries": "تحقق من قيود دفتر الأستاذ",
	"Check unallocated amount": "تحقق من المبلغ غير المخصص",
	"Check fulfillment status": "تحقق من حالة التنفيذ",
	"Check Job Order linkage": "تحقق من ربط أمر العمل",
	"Diagnose rental status": "شخّص حالة الإيجار",
	"Check Rental Order link": "تحقق من ربط أمر الإيجار",
	"Summarize this customer": "لخّص هذا العميل",
	"Check outstanding balance": "تحقق من الرصيد المستحق",
	"Summarize this item": "لخّص هذا الصنف",
	"Check stock levels": "تحقق من مستويات المخزون",
	"Why are these records here?": "لماذا هذه السجلات هنا؟",
	"What do the columns mean?": "ماذا تعني الأعمدة؟",
	"What can I do on this list?": "ماذا يمكنني فعله في هذه القائمة؟",
	"Why are these invoices here?": "لماذا هذه الفواتير هنا؟",
	"Show unpaid invoices": "اعرض الفواتير غير المدفوعة",
	"Why are these customers here?": "لماذا هؤلاء العملاء هنا؟",
	"What does this report show?": "ماذا يعرض هذا التقرير؟",
	"Why is this total high?": "لماذا هذا الإجمالي مرتفع؟",
	"Explain the filters": "اشرح عوامل التصفية",
	"Explain this balance": "اشرح هذا الرصيد",
	"Who owes the most?": "من يدين بأكبر مبلغ؟",
	"What do we owe?": "كم علينا من ديون؟",
	"Which items are low?": "أي الأصناف منخفضة؟",
	"What is this page for?": "ما غرض هذه الصفحة؟",
	"What can I do here?": "ماذا يمكنني فعله هنا؟",
	"What page am I on?": "في أي صفحة أنا؟",
	"Where should I go to analyze a document?": "إلى أين أذهب لتحليل مستند؟",
	"Navigate to a document to analyze it": "انتقل إلى مستند لتحليله",
	"What can I analyze on this page?": "ماذا يمكنني تحليله في هذه الصفحة؟",
	"Summarize selling activity": "لخّص نشاط المبيعات",
	"Summarize buying activity": "لخّص نشاط المشتريات",
	"Check stock implications": "تحقق من آثار المخزون",
	"Check accounting impact": "تحقق من الأثر المحاسبي",
	"What should I check?": "ماذا يجب أن أتحقق منه؟",
	"Explain each settings tab": "اشرح كل تبويب إعدادات",
	"How do API keys work here?": "كيف تعمل مفاتيح API هنا؟",
	"What should I configure first?": "ماذا أهيّئ أولاً؟",
	"What is Pilot Settings for?": "ما غرض إعدادات الطيار؟",
	"What is a DocType?": "ما هو نوع المستند؟",
	"How do I add a custom field?": "كيف أضيف حقلًا مخصصًا؟",
	"How do workflows work?": "كيف تعمل سير العمل؟",
	"How do I set up permissions?": "كيف أضبط الصلاحيات؟",
	"How do I add a GSTIN field?": "كيف أضيف حقل GSTIN؟",
	"How do I set a credit limit?": "كيف أضبط حد الائتمان؟",
	"How do I link contacts?": "كيف أربط جهات الاتصال؟",
	"How do I create a Sales Order?": "كيف أنشئ أمر مبيعات؟",
	"What happens when I submit this?": "ماذا يحدث عند الإرسال؟",
	"How do I apply a discount?": "كيف أطبق خصمًا؟",
	"How do I create a credit note?": "كيف أنشئ إشعار دائن؟",
	"How do I record a partial payment?": "كيف أسجل دفعة جزئية؟",
	"How do I create a new customer?": "كيف أنشئ عميلًا جديدًا؟",
	"How do I filter by territory?": "كيف أصفّي حسب المنطقة؟",
	"How do I export this list?": "كيف أصدّر هذه القائمة؟",
	"How do I bulk update?": "كيف أنفّذ تحديثًا جماعيًا؟",
	"How do I create a new invoice?": "كيف أنشئ فاتورة جديدة؟",
	"How do I filter unpaid invoices?": "كيف أصفّي الفواتير غير المدفوعة؟",
	"How do I see overdue invoices?": "كيف أرى الفواتير المتأخرة؟",
	"How do I do a stock transfer?": "كيف أنفّذ نقل مخزون؟",
	"How do I check stock levels?": "كيف أتحقق من مستويات المخزون؟",
	"What is a Stock Entry?": "ما هو إدخال المخزون؟",
	"How do I set a reorder level?": "كيف أضبط حد إعادة الطلب؟",
	"How do I reconcile a bank statement?": "كيف أسوّي كشف بنكي؟",
	"How do I create a Journal Entry?": "كيف أنشئ قيد يومية؟",
	"How do I record a payment?": "كيف أسجل دفعة؟",
	"How do I view the general ledger?": "كيف أعرض دفتر الأستاذ العام؟",
	"How do I filter this report?": "كيف أصفّي هذا التقرير؟",
	"How do I export report data?": "كيف أصدّر بيانات التقرير؟",
}

LOCALE_CHIP_TRANSLATIONS = {
	"ckb": CHIP_TRANSLATIONS_CKB,
	"ar": CHIP_TRANSLATIONS_AR,
}

BUILD_LABEL_BY_LOCALE = {
	"ckb": BUILD_LABEL_CK,
	"ar": BUILD_LABEL_AR,
}

ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")
KURDISH_SPECIFIC_RE = re.compile(r"[ۆێڵڕئۊۋ]")


def get_ui_bundle(langs):
	bundle = {}
	for lang in langs:
		if lang in UI_STRINGS:
			bundle[lang] = dict(UI_STRINGS[lang])
	return bundle


def _chip_prompt_text(chip) -> str:
	if isinstance(chip, dict):
		return chip.get("prompt") or chip.get("label") or ""
	return chip or ""


def chip_mode(prompt_en):
	prompt = _chip_prompt_text(prompt_en)
	if isinstance(prompt_en, dict) and prompt_en.get("mode"):
		return prompt_en["mode"]
	return "diagnose" if prompt in DIAGNOSE_PROMPTS else "explain"


def _english_chip(prompt_en):
	if isinstance(prompt_en, dict):
		label = prompt_en.get("label") or prompt_en.get("prompt") or ""
		return {
			"prompt": prompt_en.get("prompt") or label,
			"label": label,
			"locale": prompt_en.get("locale") or "en",
			"mode": chip_mode(prompt_en),
			"preset_id": prompt_en.get("preset_id") or "",
		}
	return {
		"prompt": prompt_en,
		"label": prompt_en,
		"locale": "en",
		"mode": chip_mode(prompt_en),
	}


def _localized_chip(prompt_en, locale):
	prompt = _chip_prompt_text(prompt_en)
	catalog = LOCALE_CHIP_TRANSLATIONS.get(locale) or {}
	label = catalog.get(prompt, "")
	if not label:
		return None
	return {
		"prompt": label,
		"label": label,
		"locale": locale,
		"prompt_en": prompt,
		"mode": chip_mode(prompt_en),
	}


def expand_split_chips(prompts_en, langs, *, max_en=4):
	"""Single-language chips: up to max_en EN, or SPLIT_CHIP_PAIRS EN + paired locale chips."""
	prompts_en = [p for p in (prompts_en or []) if p]
	if not prompts_en:
		return []

	if any(isinstance(p, dict) for p in prompts_en):
		return [_english_chip(p) for p in prompts_en[:max_en]]

	chip_locales = [loc for loc in PILOT_CHIP_LOCALES if loc in langs]
	if not chip_locales:
		return [_english_chip(p) for p in prompts_en[:max_en]]

	out = []
	for prompt_en in prompts_en[:SPLIT_CHIP_PAIRS]:
		out.append(_english_chip(prompt_en))
		for locale in chip_locales:
			chip = _localized_chip(prompt_en, locale)
			if chip:
				out.append(chip)
	return out


def localize_chips(prompts, langs):
	"""Compat wrapper — uses split-chip model."""
	return expand_split_chips(prompts, langs)


def _allowed_chip_locales(langs, sidebar_locale, scope):
	"""Locales permitted for suggestion chips / build cards under chip_locale_scope."""
	enabled = set(langs or ["en"])
	sidebar_locale = sidebar_locale or "en"
	scope = scope or "all_enabled"

	if scope == "active_locale":
		if sidebar_locale in enabled:
			return {sidebar_locale}
		return {"en"}

	if scope == "active_plus_en":
		allowed = {"en"}
		if sidebar_locale in enabled and sidebar_locale != "en":
			allowed.add(sidebar_locale)
		return allowed

	return enabled


def apply_chip_locale_scope(items, langs, sidebar_locale="en", scope="all_enabled"):
	"""Filter chips or build actions by Enabled languages and chip_locale_scope."""
	allowed = _allowed_chip_locales(langs, sidebar_locale, scope)
	enabled = set(langs or ["en"])
	out = []
	for item in items or []:
		loc = item.get("locale") or "en"
		if loc not in enabled:
			continue
		if loc in allowed:
			out.append(item)
	return out


def _build_action_localized_desc(desc, locale):
	if locale == "ckb":
		if desc.startswith("Add a field to"):
			return desc.replace("Add a field to", "خانە زیاد بکە بۆ", 1)
		if desc.startswith("Python automation on"):
			return desc.replace("Python automation on", "خۆکارکردنی پایتۆن لەسەر", 1)
		if desc.startswith("Form behaviour on"):
			return desc.replace("Form behaviour on", "ڕەفتاری فۆرم لەسەر", 1)
		if desc.startswith("Approval flow for"):
			return desc.replace("Approval flow for", "ڕێڕەوی پەسەندکردن بۆ", 1)
	elif locale == "ar":
		if desc.startswith("Add a field to"):
			return desc.replace("Add a field to", "أضف حقلًا إلى", 1)
		if desc.startswith("Python automation on"):
			return desc.replace("Python automation on", "أتمتة بايثون على", 1)
		if desc.startswith("Form behaviour on"):
			return desc.replace("Form behaviour on", "سلوك النموذج على", 1)
		if desc.startswith("Approval flow for"):
			return desc.replace("Approval flow for", "مسار الموافقة لـ", 1)
	return desc


def expand_split_actions(actions, langs):
	chip_locales = [loc for loc in PILOT_CHIP_LOCALES if loc in langs]
	if not chip_locales:
		return [dict(a, locale="en") for a in (actions or [])]

	out = []
	for action in (actions or [])[:SPLIT_CHIP_PAIRS]:
		en = dict(action)
		en["locale"] = "en"
		en["label"] = action.get("label") or ""
		en["desc"] = action.get("desc") or ""
		out.append(en)

		label = action.get("label") or ""
		for locale in chip_locales:
			loc_label = (BUILD_LABEL_BY_LOCALE.get(locale) or {}).get(label, "")
			if not loc_label:
				continue
			loc_action = dict(action)
			loc_action["locale"] = locale
			loc_action["label"] = loc_label
			loc_action["desc"] = _build_action_localized_desc(action.get("desc") or "", locale)
			loc_action["prompt_en"] = action.get("prompt") or ""
			if loc_label and action.get("prompt"):
				loc_action["prompt"] = action["prompt"]
			out.append(loc_action)
	return out


def localize_actions(actions, langs):
	return expand_split_actions(actions, langs)


def format_greet(greet_en, ctx, tab, langs, sidebar_locale="en"):
	"""Return greet for active sidebar locale only (no stacked bilingual)."""
	tab = (tab or "advisor").lower()
	if tab in ("analyze", "guide"):
		tab = "advisor"

	if sidebar_locale in PILOT_CHIP_LOCALES and sidebar_locale in langs:
		greet_fn = {"ckb": _greet_ckb, "ar": _greet_ar}.get(sidebar_locale)
		if greet_fn:
			return {"greet": greet_fn(ctx, tab), "greet_locale": sidebar_locale}
	return {"greet": greet_en, "greet_locale": "en"}


def _greet_ckb(ctx, tab):
	if tab == "guide":
		if ctx.get("doctype"):
			return f"لە فۆرمی **{ctx['doctype']}**یت. ئەمە چەند شتێکن کە دەتوانم یارمەتیت بدەم:"
		if ctx.get("list_doctype"):
			return f"لە لیستی **{ctx['list_doctype']}**یت. پرسیارێک هەڵبژێرە:"
		return "سڵاو! ڕێنمایی ERPNextم. پرسیارێک هەڵبژێرە:"
	if tab == "build":
		target = ctx.get("doctype") or ctx.get("list_doctype") or ""
		if target:
			return f"لە **{target}**یت. چی دەتەوێت دروست بکەیت؟"
		return "چی دەتەوێت لە ERPNext دروست بکەیت؟"
	if ctx.get("has_saved_doc"):
		return (
			f"دەتوانم **{ctx.get('doctype')}: {ctx.get('docname')}** "
			"بە داتای ڕاستەوخۆ شیکار بکەم. پێشنیارێک هەڵبژێرە:"
		)
	if ctx.get("doctype"):
		return f"فۆرمی نوێی **{ctx['doctype']}**. خانەکان ڕوون دەکەمەوە:"
	if ctx.get("list_doctype") or ctx.get("page_type") == "list":
		dt = ctx.get("list_doctype") or ""
		return f"لیستی **{dt}**. بۆچی ئەم تۆمارانە لێرەن دەتوانم ڕوون بکەمەوە:"
	if ctx.get("report_name") or ctx.get("page_type") == "report":
		rn = ctx.get("report_name") or "ڕاپۆرت"
		return f"ڕاپۆرتی **{rn}**. ئەنجامەکان ڕوون دەکەمەوە:"
	return "بچۆ بۆ تۆمار، لیست یان ڕاپۆرت بۆ شیکردنەوە:"


def _greet_ar(ctx, tab):
	if tab == "guide":
		if ctx.get("doctype"):
			return f"أنت في نموذج **{ctx['doctype']}**. إليك بعض الأمور التي يمكنني مساعدتك بها:"
		if ctx.get("list_doctype"):
			return f"أنت في قائمة **{ctx['list_doctype']}**. اختر سؤالًا:"
		return "مرحبًا! أنا دليل ERPNext. اختر سؤالًا:"
	if tab == "build":
		target = ctx.get("doctype") or ctx.get("list_doctype") or ""
		if target:
			return f"أنت في **{target}**. ماذا تريد أن تبني؟"
		return "ماذا تريد أن تبني في ERPNext؟"
	if ctx.get("has_saved_doc"):
		return (
			f"يمكنني تحليل **{ctx.get('doctype')}: {ctx.get('docname')}** "
			"ببيانات مباشرة. اختر اقتراحًا:"
		)
	if ctx.get("doctype"):
		return f"نموذج **{ctx['doctype']}** جديد. سأشرح الحقول:"
	if ctx.get("list_doctype") or ctx.get("page_type") == "list":
		dt = ctx.get("list_doctype") or ""
		return f"قائمة **{dt}**. يمكنني شرح سبب وجود هذه السجلات هنا:"
	if ctx.get("report_name") or ctx.get("page_type") == "report":
		rn = ctx.get("report_name") or "تقرير"
		return f"تقرير **{rn}**. سأشرح النتائج:"
	return "انتقل إلى مستند أو قائمة أو تقرير للتحليل:"


def build_chip_meta(chips):
	"""Compat shim: prompt -> mode for legacy clients."""
	meta = {}
	for chip in chips:
		if isinstance(chip, dict):
			if chip.get("mode") == "diagnose":
				key = chip.get("prompt_en") or chip.get("prompt") or ""
				meta[key] = {"mode": "diagnose"}
				meta[chip.get("prompt") or ""] = {"mode": "diagnose"}
			elif chip.get("mode") == "insight_preset" or chip.get("preset_id"):
				key = chip.get("prompt_en") or chip.get("prompt") or chip.get("label") or ""
				entry = {
					"mode": "insight_preset",
					"preset_id": chip.get("preset_id") or "",
				}
				meta[key] = entry
				meta[chip.get("prompt") or chip.get("label") or ""] = entry
		elif chip in DIAGNOSE_PROMPTS:
			meta[chip] = {"mode": "diagnose"}
	return meta


def _language_display_name(code):
	name = frappe.db.get_value("Language", code, "language_name")
	if name:
		return name
	if code == "ckb":
		return "Kurdish Sorani"
	if code == "ar":
		return "Arabic"
	return code


def get_llm_language_instruction(langs):
	extra = [code for code in langs if code and code != "en"]
	if not extra:
		return ""

	lines = ["\n\n## Language"]
	for code in extra:
		if code == "ckb":
			lines.append(
				"Reply in Kurdish Sorani (Central Kurdish, Arabic script). "
				"When the user says \"Kurdish\" or writes in Kurdish script, treat it as Kurdish Sorani "
				"(not Kurmanji/Badini). Understand user messages in Kurdish Sorani."
			)
		elif code == "ar":
			lines.append(
				"Reply in Modern Standard Arabic (العربية الفصحى). "
				"Understand user messages in Arabic."
			)
		else:
			name = _language_display_name(code)
			lines.append(
				f"When the user's locale is {code} ({name}), reply in {name}. "
				f"Understand user messages in {name}."
			)
	lines.append(
		"Keep ERPNext DocType names, field names, and document IDs in English. "
		"Be clear and concise."
	)
	return "\n".join(lines)


def detect_user_locale(message, enabled_langs):
	text = (message or "").strip()
	if not text:
		return None
	lower = text.lower()
	if "ckb" in enabled_langs:
		for alias in KURDISH_SORANI_ALIASES:
			if alias in lower:
				return "ckb"
	if ARABIC_SCRIPT_RE.search(text):
		if "ckb" in enabled_langs and KURDISH_SPECIFIC_RE.search(text):
			return "ckb"
		if "ar" in enabled_langs:
			return "ar"
		if "ckb" in enabled_langs:
			return "ckb"
	return None


def locale_context_note(user_locale):
	if not user_locale or user_locale == "en":
		return ""
	if user_locale == "ckb":
		return "[User locale: Kurdish Sorani — reply in Sorani.]\n"
	if user_locale == "ar":
		return "[User locale: Arabic (العربية) — reply in Modern Standard Arabic.]\n"
	name = _language_display_name(user_locale)
	return f"[User locale: {name} ({user_locale}) — reply in {name}.]\n"
