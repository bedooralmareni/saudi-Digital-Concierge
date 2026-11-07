# Saudi Digital Concierge — Scenario set v1.0

هذه الحزمة تحتوي على 100 سيناريو اصطناعي مبني على نسخة قاعدة البيانات المرفقة، مع إجابات مرجعية قابلة للتحقق. لا تحتوي على نتائج تشغيل النماذج أو كود تقييم إجاباتها.

| Split | Typical | Edge | Arabic | English | Total |
|---|---:|---:|---:|---:|---:|
| Development | 42 | 18 | 30 | 30 | 60 |
| Validation | 14 | 6 | 10 | 10 | 20 |
| Final Test | 14 | 6 | 10 | 10 | 20 |
| Total | 70 | 30 | 50 | 50 | 100 |

## البدء

1. ابدئي بملف `development/prompts.csv` أو `development/prompts.jsonl`. كل سؤال بلغة واحدة؛ لا توجد نسختان مترجمتان محسوبتان كسيناريوهين.
2. أضيفي تعليمات السياق المناسبة للغة من `manifest.json` إلى تعليمات التشغيل المشتركة. تطبَّق التعليمات نفسها على الـBaseline والنظام متعدد الوكلاء. احتفظي بالصيغة المختارة دون تغيير بينهما.
3. أعطي النموذج قاعدة البيانات والأسئلة فقط. لا تُدخلي ملفات `gold.json` أو ملف Excel أو النتائج المرجعية في سياقه أو أدوات البحث الخاصة به.
4. استخدمي Development للتطوير، وValidation لاختيار الإعدادات، ثم جمّدي الإعدادات قبل فتح Final Test للتقييم النهائي. فصل المجلدات إجراء تنظيمي وليس حماية وصول تقنية.
5. الخطوة التالية في M5 هي تثبيت صيغة مخرجات النموذج وكتابة كود التقييم وتسجيل المسار، ثم تشغيل ثلاثة seeds محددة مسبقًا. لم تُنفّذ هذه الخطوات ضمن حزمة السيناريوهات.

## What each file contains

- `manifest.json`: database fingerprint, split quotas, version and shared system context.
- Each split has `prompts.csv` and `prompts.jsonl` with only scenario ID, language and prompt.
- Each split has `gold.json` with status, constraints encoded by parameterized SQL, all admissible record IDs, supporting records and behavioral criteria.
- `verify_ground_truth.py` re-executes all SQL and checks quotas, IDs, NULL evidence, linked-group isolation and source hash. It uses Python's standard library only.
- `validation_report.json` records benchmark-validation checks. PASS does not mean a model passed.

Run from the extracted package:

```bash
python verify_ground_truth.py /path/to/knowledge_base.sqlite
```

The source database itself is not duplicated in the ZIP. Use the supplied `knowledge_base.sqlite` with SHA-256 `cdbd4c20632e57c87d2ffb3ef97f603bfd1150cbb0ee38a297e2ce736f08c986`.

## Scope and interpretation

This is an offline, synthetic, closed-world recommendation benchmark over one database snapshot. It covers accommodation, food venues, entertainment venues, events and 20 typical composite hotel/activity or hotel/event requests, plus partial-completion edge cases. It does not establish live travel feasibility, opening hours, booking availability, transport times, or complete trip cost. It is not a comprehensive multi-day itinerary benchmark.

Hotel attributes/prices come from the 2020-04-24 snapshot. `price_sar` is treated as the recorded price of the listed option, not an independently verified nightly rate. Do not multiply it by people or nights. A matching `max_persons` establishes only recorded capacity. Breakfast/cancellation NULL means unknown. Do not infer room availability for the event date, or that a hotel existed in that year. Historical visit questions intentionally combine static accommodation attributes with dated event records as an offline selection exercise, not a historical booking reconstruction.

Events use the 2026-09-13 snapshot. Month questions explicitly test events **starting** within the month, not every event overlapping it. No start/end filters depend on the execution clock. X30 alone fixes its reference date to 2026-11-06 and tests stale `is_active` against recorded dates. Dates extending years into the future are not independent confirmation of real operation.

The places table is Riyadh-only. Filter `granular_category='restaurants'` before interpreting exact pipe-delimited category tags. `is_restaurant` alone is unreliable. Food venues can include cafes/dessert shops, as specified in the prompts. No meal-price or opening-hours fields exist. Hotels use the guest-rating scale /10; places and entertainment use /5; star classification is a separate field.

## Ground truth and acceptance criteria

For a recommendation component, `accepted_ids` contains the complete set of rows satisfying its SQL constraints. The selected first record or the workbook example is not the only correct answer. Returning the requested number of different admissible choices is enough; the model need not enumerate all matches. Enforce exact requested counts unless a case explicitly requests partial completion. Any extra proposed option must be clearly labelled outside the compliant answer.

Distinctness is defined operationally as normalized name + city. For events it also includes start and end dates, so separate dated editions remain separate. `distinct_option_groups` lists IDs that count once under this rule. This is a conservative diversity rule, not proof of real-world entity identity: different branches with identical names in one city may be collapsed. IDs remain available as alternate acceptable references. Do not require the model to infer canonical entity IDs.

For `unknown`/`lookup` components, `supporting_ids` and `evidence` support the answer but are not recommendation candidates; `accepted_ids` is empty by design. For `no_match`, the SQL result must be empty. `required_count=0` in these modes does not mean the user asked for zero results; it indicates that no compliant recommendation should be produced. For X25 the user asks for three places, but only one distinct option is supported, so the component's acceptable returned count is one and the required status is PARTIAL.

| Expected status | Required interpretation |
|---|---|
| MATCH | Satisfy every stated component, count and hard constraint. |
| NO_MATCH | No matching record in this snapshot; do not claim real-world nonexistence. |
| COVERAGE_GAP | Requested city/type is outside the relevant table's coverage. |
| INSUFFICIENT_DATA | A required field is NULL, absent, or cannot confirm live facts. |
| CLARIFY | Ask for the missing/corrected information before making definitive recommendations. |
| PARTIAL | Complete supported parts and explicitly identify the unmet or unverifiable parts. |
| NOT_ONGOING | Recorded end date is before the fixed question date despite a stale active flag. |

Content must match the supporting record: IDs, names, city, requested prices, capacities, ratings, flags and dates. Do not score stylistic paraphrases as factual differences. Different admissible options are equally correct unless ranking is explicitly requested; no case requires ranking. Explain constraint compliance where requested, preserve qualifiers, and answer in the prompt language.

Behavioral criteria in `behavior` are evaluator-only instructions. They are not model prompts. A future automated scorer should combine deterministic ID/field/count checks with separately validated checks of clarification, uncertainty and unsupported claims. A status label alone is not proof of correct behavior. Cases with no SQL components are evaluated against documented request logic or schema limitations.

For the next M5 step, report recommendation constraint satisfaction, component completion and whole-case success separately; retain failure categories. Do not report this script as response scoring. Trajectory-level evaluation also requires runtime logs; one operational candidate is failed tool calls divided by total tool calls, with zero tool calls treated as not applicable rather than automatically perfect. The metric and logging contract still need to be finalized with the actual system.

## Split design and limits

Split assignment is deterministic (seed 683), grouped and stratified to exact type/language quotas. Related activity-only/composite tasks and event-only/composite tasks for the same city stay together. Related restaurant-coverage and low-Riyadh-budget edge variants also stay together. Each split includes all six broad typical task domains and at least one NO_MATCH, INSUFFICIENT_DATA, CLARIFY and PARTIAL case.

Typical domain balance is also exact:

| Domain | Development | Validation | Final Test | Total |
|---|---:|---:|---:|---:|
| Hotels | 12 | 4 | 4 | 20 |
| Restaurants | 6 | 2 | 2 | 10 |
| Entertainment | 6 | 2 | 2 | 10 |
| Events | 6 | 2 | 2 | 10 |
| Hotel + activity | 6 | 2 | 2 | 10 |
| Hotel + event | 6 | 2 | 2 | 10 |

Exact prompt texts and complete query signatures are unique. No translated duplicates are included. The benchmark still shares templates, cities and database entities between splits; it is not an entity-disjoint or template-disjoint generalization test, and no formal semantic paraphrase detector was used. Broader semantic overlap and domain balance should be discussed as limitations. The data is heavily concentrated in Riyadh/Jeddah, and restaurant requests are necessarily Riyadh-focused. Do not interpret results as representative of all Saudi tourism tasks.

Source: user-supplied `knowledge_base.sqlite`. Source fields and links in that database retain original provenance. This package does not independently verify external sources or licenses. Requirements context: CPCS683 Project Description and Milestones, M5, and Project grading rubric C5.1–C5.4.
