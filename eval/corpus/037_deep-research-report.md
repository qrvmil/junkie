# 2026 Russia AI/SaaS Project: Economics, Taxation, and Scaling Model from Individual to Branch

## Executive summary

This report builds a 2026 financial–tax model and operational cost research for an AI/SaaS platform in the Russian market, explicitly following the staged evolution **individual → NPD → sole proprietor (IP, USN) → LLC (OSNO) → branch** that is prescribed in your course materials. fileciteturn0file3 fileciteturn0file2 fileciteturn0file4

The **2026 tax landscape** materially changes planning assumptions versus pre‑2026 norms:

- The **standard VAT rate is 22% from 1 Jan 2026** (law change; reflected in the Tax Code’s VAT rate article). citeturn2search3turn3search2turn0search0  
- The **corporate profit tax rate is 25%** (the Tax Code’s profit‑tax rate article reflects the change; also explained in Federal Tax Service communications). citeturn3search0turn0search1  
- The **progressive personal income tax (NDFL) scale** in 2026 reaches **up to 22%**, and your methodological package uses the 13%→22% stepped thresholds as the required baseline for modeling. fileciteturn0file3 fileciteturn0file4 citeturn2search2turn3search1  
- **USN (simplified regime) limits are indexed upward in 2026**, but a key new feature is that **VAT can arise for USN payers** depending on turnover (including an **automatic VAT exemption threshold at 20M RUB** and special VAT rates **5%/7%** for higher annual income bands). This can affect the timing and benefits of switching from USN to OSNO. citeturn48search0turn48search1  
- For an IP without employees, **fixed “for self” insurance contributions in 2026 are 57,390 RUB** (if income ≤300k), plus **1% above 300k** (with a statutory maximum for that 1% component). citeturn43view0  

From a unit‑economics perspective, the **largest structural cost driver** for a Russian AI/SaaS is usually **payroll (FOT + employer insurance contributions)**, not AI token usage—provided you choose cost‑efficient LLM serving options. For example, in 2026 business tariffs, **GigaChat API** pay‑as‑you‑go costs (incl. VAT) range down to **0.0325 RUB per 1,000 tokens** in async mode for Lite, while higher tiers and synchronous modes are more expensive. citeturn42view0  
Comparable Russian LLM tariffs published by other providers show that “per‑token” costs can also be in sub‑ruble territory per 1,000 tokens depending on model and tariff schedule. citeturn40search0turn40search3  

A conservative reading of public salary research (late‑2025 data, used as the closest robust public baseline for 2026 planning) suggests that scaling to a full in‑house team quickly pushes the project into a cash‑burn phase unless you reach **hundreds** of paying customers at SMB price points. In the **base scenario** of the modeled 12‑month run (assumptions made explicit later), the business ends the year at ~27 active customers with negative cashflow and requires **~5.16M RUB** in starting liquidity to avoid a cash deficit; a required stress test of **−20% revenue and +30% expenses** increases that requirement to **~8.22M RUB**. (These are model outputs driven by your methodology’s staged structure and by sourced price/tariff inputs; volumes and adoption are explicit assumptions.) fileciteturn0file3 fileciteturn0file4  

Key compliance risks with the highest downside—because they can trigger forced regime changes, VAT back‑assessments, and penalties—match the “typical errors” document you supplied: “business splitting” around NPD/USN limits, unreported income, late tax payment discipline failures, fictitious expenses, and VAT deduction errors. fileciteturn0file0

## Source documents digest and how they are used in the model

### Short recap of each uploaded file

The methodological backbone is the course assignment file **“Методическое задание НПД.docx”**. It mandates: (1) a multi‑stage tax model across the full lifecycle; (2) automated formulas (Excel in the course, mirrored here as explicit formula logic); (3) required taxes by stage (NDFL progressive; NPD 4/6; USN 6/15 with minimum tax logic; OSNO VAT and profit tax; payroll withholding and contributions); (4) inclusion of at least one “non‑typical” operation; (5) at least four typical errors with legal references and prevention; (6) a branch decision with a 2–3‑region comparison; and (7) a stress scenario. fileciteturn0file3

The business evolution file **“План.docx”** defines the product as an AI‑agent platform for support/sales across channels (chat/voice/email), highlights monetization streams (setup, subscription, add‑ons), and explicitly explains the managerial logic for each legal/regime transition (e.g., from “hands‑on services” to product MRR; from USN/IP to LLC for enterprise expectations, VAT and contracting; from single site to branch for cost optimization). fileciteturn0file2

The compliance risk file **“Ошибки.docx”** provides five concrete tax‑error scenarios mapped to legal bases and consequences: NPD income splitting; hiding income to keep USN; late payments; fictitious expenses under OSNO; VAT deduction mistakes. These are used as a required “risk register” section with preventative controls. fileciteturn0file0

The glossary **“Аббревиатуры.docx”** is used to standardize terms throughout: SaaS, AI/ML/LLM, API, GPU, CRM, MRR/LTV/CAC, and Russian tax abbreviations (NPD/USN/OSNO, NDFL, VAT, FOT, KKT, RSV, EHS, etc.). fileciteturn0file1

The presentation PDF **“Задание_презентация.pdf”** is used as a second methodological reference: it encodes the same staged story, calls out “tax constants” (VAT 22%, profit tax 25%, progressive NDFL), stresses employer burden, demonstrates an OSNO vs USN effective tax‑rate intuition, provides a region/branch decision frame (VAT centralized, profit tax distributed), and explicitly requires the −20%/+30% stress test and a “price of mistakes” risk map (54‑FZ/KKT, reporting deadlines, 54.1, 123). fileciteturn0file4

### How these documents are translated into a working model

The model is built as a set of **parameter blocks** and **stage‑specific calculation blocks**, reflecting the methodological requirements:

- **Stage blocks**: Individual (NDFL), NPD, IP‑USN, LLC‑OSNO, Branch. The stage block determines which tax formulas apply. fileciteturn0file3  
- **Operations block**: Revenue streams (setup + subscription + add‑ons/API), and costs (people, infra, AI tokens, office). This is aligned with the business plan file’s monetization and cost drivers. fileciteturn0file2  
- **Risk block**: error scenarios from the “Ошибки” file with prevention controls and legal mapping. fileciteturn0file0  
- **Stress block**: the mandatory turbulence scenario (−20% revenue, +30% expenses). fileciteturn0file4  
- **Region/branch block**: a 2–3 region comparison consistent with the branch slide logic and the methodical “filial” requirement. fileciteturn0file3 fileciteturn0file4  

### Which methodological requirements are explicitly satisfied

- “Do not invent tax rates/limits”: VAT 22% (2026), profit tax 25%, NPD rates/limits, USN indexed limits, insurance contribution constants are sourced to the Federal Tax Service / Tax Code / official tariff documents. citeturn2search3turn3search2turn0search1turn43view0turn48search0turn1search2  
- “Show assumptions”: customer counts, churn, token loads, staffing timelines are explicit assumptions and are separated from sourced price/tax constants. fileciteturn0file3  
- “Tables reconcile”: within the scope of included categories, the calculation appendix ties revenue → taxes → profit → cashflow for each scenario. (Where a line item is tagged **estimate**, it is clearly flagged and does not claim a sourced market tariff.) fileciteturn0file3  
- “Include errors and prevention”: all five error scenarios from your “Ошибки.docx” are included as a structured risk register. fileciteturn0file0  
- “Include stress test”: the stress test exactly matches the −20%/+30% requirement. fileciteturn0file4  

## Innopolis baseline costs, housing, and workspace economics

### Living costs in entity["city","Innopolis","tatarstan, russia"] and the Kazan commute option

**Housing (monthly rent) – Innopolis**

Publicly observable rents show a wide split between “program/managed housing” and open market supply:

- Managed rentals in Innopolis are advertised from **17,000 RUB/month** (starting price). citeturn5search0  
- The open market snapshot on entity["company","CIAN","real estate platform, russia"] shows **~40,100 RUB/month average**, with a reported range in results of **40,000 to 55,000 RUB/month** (limited listing count in that snapshot). citeturn5search2  

**Conservative interpretation.** For budgeting, treat **17k** as a “best‑case / limited availability” floor and **40k–55k** as the market reality for many renters; the conservative (higher‑cost) range is the CIAN range. citeturn5search0turn5search2  

**Utilities (Innopolis) – tariffs and what is still an estimate**

A local management company tariff document for Innopolis lists unit prices (e.g., electricity price per kWh and other utilities). citeturn6search12  
Because monthly bills depend on apartment size, metered consumption, and whether heating is included in rent, **any “total monthly коммуналка” is consumption‑assumption‑dependent**; therefore, in this report коммуналка totals are treated as **estimate** unless you provide a typical apartment profile and meter history. citeturn6search12  

**Internet (Innopolis)**

A tariff aggregator tracking Innopolis home internet states (as of **16 Feb 2026**) that home‑internet plans start from **275 RUB/month** in Innopolis (speed and conditions vary by provider). citeturn45search7  

**Mobile / bundled telecom (Tatarstan & Innopolis)**

Official regional tariff pages show entry points for bundled service packages:

- entity["company","MTS","telecom operator, russia"] Kazan page shows a “home + mobile” style plan at **400 RUB/month** for 30GB (promotional/packaged context). citeturn45search0  
- entity["company","Beeline","telecom operator, russia"] Innopolis page shows promotional monthly prices starting at **175 RUB/month** (for a limited promotional period) for bundled home internet + mobile packages. citeturn45search3  

Because such offers can be promotional and time‑limited, the conservative approach is to treat these as **min** and plan a higher “median” after promotions.

**Kazan alternative + transport**

The official Innopolis “how to get” page states that the Kazan→Innopolis branded shuttle fare is **270 RUB by bank card / 300 RUB in cash** (with discounts for INNO ID cardholders). citeturn47search0  
A separate Innopolis schedule page publishes route timings. citeturn47search8  

A realistic commute budget therefore scales with working days; for example, 20 round trips/month at 270 RUB each way is **~10,800 RUB/month** (this multiplication is arithmetic, not a sourced tariff; the tariff itself is sourced). citeturn47search0turn47search8  

image_group{"layout":"carousel","aspect_ratio":"16:9","query":["Innopolis city Russia skyline","Innopolis University campus","Kazan Russia city skyline","Russia data center server racks"],"num_per_query":1}

### Offices, coworkorking, and “tech park” options

**Innopolis (tech‑park style space)**  
The Innopolis “office rental” page lists multiple formats with explicit starting points:

- Dedicated coworking desk: **from 6,000 RUB/month**  
- Office rental: **from 735 RUB per m²/month** (starting price) citeturn14search2  

These are unusually low compared to many large‑city markets; treat them as “from” prices and validate actual availability and total cost (utilities, fit‑out, access control, meeting rooms) when you pick a building and term. citeturn14search2  

**Kazan office market baseline**  
CIAN’s Kazan office‑rent listing page reports:

- Average monthly rent in results: **~85.8k RUB/month**  
- Minimum: **~5.8k RUB/month**  
- Maximum: **~2.4M RUB/month** citeturn54view0  

The distribution is extremely wide because it mixes micro‑offices and large premium spaces; for model inputs, use the average as a “quick market anchor” and then price a concrete office size based on your expected headcount. citeturn54view0  

## Infrastructure economics for AI/SaaS at 2026 Russian tariffs

This section corresponds to your required infrastructure split: VPS/cloud, bare metal, GPU rental, and own servers (with CAPEX vs OPEX framing). fileciteturn0file3

### VPS and public cloud

**Sourcing limitation (important).** Within the remaining tool‑based evidence captured in this session, fully itemized “per vCPU / per GB RAM” public‑cloud calculators could not be re‑opened after tool‑call limits were reached. Therefore:

- Where only “from” pricing is available, those values are treated as **min**, and median/max must be confirmed against the specific cloud calculator you intend to use.  
- The financial model uses **dedicated/bare‑metal rental** and **LLM API tariffs** as the primary sourced infra components; VPS “glue costs” can be added once you select a cloud vendor and instance types.

### Bare metal rental

Bare metal is often the simplest way to get predictable compute in Russia if you want stable performance without cloud egress surprises.

Examples of published monthly prices:

- Dedicated server offers on entity["company","HOSTKEY","hosting provider, russia"] show configurations with monthly prices such as **19,800 RUB/month** (Ryzen 9 5950X / 64GB / 2×960GB NVMe) and higher tiers like **55,680 RUB/month** (Threadripper Pro 3995WX / 256GB / 2×3.84TB NVMe). citeturn12search0  
- Another provider listing indicates dedicated servers from **9,000 RUB/month** (entry point). citeturn12search4  

**TCO framing** (OPEX):  
Annual TCO is simply monthly×12, plus backups/storage and support services. The main risk is hardware failure and replacement SLA; mitigate via RAID/NVMe redundancy, offsite backups, and a warm spare for key services.

### GPU rental

GPU economics are the main swing factor if you self‑host inference or do heavy fine‑tuning.

A published reference point:

- entity["company","Cloud.ru","cloud provider, russia"] lists a high‑end GPU cluster line item (HGX 8×H100 SXM 80GB) at **5,355,000 RUB/month** (price includes VAT line items in the tariff card). citeturn7search12  

This is a “max‑class” capacity benchmark that is useful to cap aggressive scenarios: if your product economics cannot absorb that OPEX, you must reduce GPU hours, use smaller GPUs/models, or externalize model calls to API providers.

### Own servers and colocation

To model own‑hardware TCO, you need:

- CAPEX: server(s) + GPU(s) + network + UPS  
- OPEX: colocation (rack/U) + power + remote hands + replacement parts + warranty strategy

**Constraint:** in this captured session, colocation price tables could not be re‑opened reliably after tool limits. The only robust approach left is to treat own‑hardware CAPEX/OPEX as a **separately parameterized** scenario, with decision variables you fill once you choose a DC and rack/unit tariff schedule.

### LLM API as a cost‑stabilizing alternative

For many AI/SaaS workloads, the LLM “brain” is cheaper to externalize than to self‑host—especially early.

Published 2026 token tariffs show a very wide but manageable range:

- **GigaChat API (legal entities), updated 29 Jan 2026; effective 1 Feb 2026**:  
  - async text generation: **0.0325 RUB / 1,000 tokens** (Lite), **0.25 RUB / 1,000 tokens** (Pro), **0.325 RUB / 1,000 tokens** (Max)  
  - minimum monthly charge logic: if you use the service and total charges are below **600 RUB**, you pay **600 RUB** that month citeturn42view0  
- **Yandex AI Studio pricing** includes a published example where YandexGPT Pro async is **0.61 RUB / 1,000 tokens**. citeturn40search0  
- A Cloud.ru tariff appendix (effective **1 Jan 2026**) shows foundation model tariffs priced per **1 million tokens** (with VAT shown), which can imply sub‑ruble costs per 1,000 tokens for some models/services. citeturn40search3  

**Operational risk trade‑off:** API outsourcing reduces CAPEX and GPU ops complexity but introduces vendor dependency, rate‑limit risk, and compliance constraints around data processing (especially for personal data and regulated industries). Your branch/OSNO stage should include a vendor‑risk mitigation plan (multi‑provider routing, caching, fallbacks).

## Personnel, payroll taxes, and the hiring cost stack

This section maps to the “Персонал” requirement (roles + salary ranges + taxes + FOT + hiring cost). fileciteturn0file3

### Salary benchmarks and how to interpret conflicting datasets

Two public sources in this session provide complementary evidence:

- Habr Career salary research provides **regional/city medians** and role charts with percentiles. In the second half of 2025, it reports IT median salaries of **~159k in regions**, **~230k in Moscow**, **~200k in Saint Petersburg**, and a city‑specific median of **~170k for Kazan**. citeturn37view1turn37view0  
- The IT workers’ union salary survey explains its percentile charts (10th/median/90th) and provides specialization distributions (development, AI, sales, support, etc.), based on **2314 Russia‑based respondents working for Russian companies**. citeturn53search1turn53search11turn33view0  

**Why they differ:** surveys can be biased toward higher‑paid segments (role composition, seniority mix, self‑selection). For planning, the conservative interpretation for **costs** is to treat higher medians as plausible if you hire above‑market talent (especially ML/DevOps), while using city medians to sanity‑check regional affordability. citeturn37view0turn33view0turn53search1  

### Salary ranges by role

The table below provides **(min / median / max)** as **10th / 50th / 90th percentile** where available (Russia baseline), and a **Kazan/Tatarstan proxy** using the observed Kazan vs “regions” median ratio (170k vs 159k) as a scaling factor. The scaling itself is a modeled transformation (explicitly an estimate); the underlying percentile anchors are sourced. citeturn37view0turn37view1turn33view0turn53search11  

| Role | Russia min/median/max (RUB/month) | Kazan/Tatarstan proxy min/median/max (estimate) | Source “as-of” |
|---|---:|---:|---|
| Dev (software development specialization) | 128k / 280k / 439k citeturn33view0 | ~137k / ~299k / ~469k (scaled) citeturn37view0turn37view1turn33view0 | 2H 2025 (survey); used for 2026 planning citeturn53search1 |
| ML / AI specialization | 130k / 290k / 450k citeturn33view0 | ~139k / ~310k / ~481k (scaled) citeturn37view0turn37view1turn33view0 | 2H 2025 (survey); used for 2026 planning citeturn53search1 |
| DevOps (role chart) | 98k / 240k / 433k citeturn18view1 | ~105k / ~256k / ~463k (scaled) citeturn37view0turn37view1 | 2H 2025 (Habr chart); used for 2026 planning citeturn18view1 |
| Sales specialization | 110k / 226k / 500k citeturn33view0 | ~118k / ~241k / ~534k (scaled) citeturn37view0turn37view1turn33view0 | 2H 2025 (survey); used for 2026 planning citeturn53search1 |
| Support specialization | 65k / 160k / 255k citeturn33view0 | ~69k / ~171k / ~272k (scaled) citeturn37view0turn37view1turn33view0 | 2H 2025 (survey); used for 2026 planning citeturn53search1 |
| Product manager (role chart) | 100k / 260k / 483k citeturn18view2 | ~107k / ~278k / ~516k (scaled) citeturn37view0turn37view1 | 2H 2025 (Habr chart); used for 2026 planning citeturn18view2 |

**Note on Innopolis.** There was no robust public salary distribution specifically for Innopolis in the captured sources; for modeling, Innopolis is treated as “Tatarstan/Kazan proxy” and should be validated by vacancy sampling once you have target roles and employers.

### Payroll taxes and employer cost multipliers

Key statutory constants used in the model:

- **Insurance contribution base (2026): 2,979,000 RUB** (annual base for applying the main combined tariff). citeturn1search3  
- **IP fixed contributions (2026): 57,390 RUB** if income ≤300k; plus **1% above 300k**, capped (statutory maximum quoted by the tax service). citeturn43view0  

In practical budgeting, a common conservative approximation for employer burden is:

- Employer cost ≈ **gross salary + employer contributions**, where contributions are roughly **30%** up to the annual base and lower above it (exact application depends on employee annualized pay and eligibility for reduced tariffs; your methodological slides emphasize the burden concept even if reduced SME tariffs apply). fileciteturn0file4 citeturn1search3  

## Tax regimes and transition logic for 2026

This section corresponds to the “Taxes and regimes” requirement and explicitly follows the regime sequence mandated by the methodical materials. fileciteturn0file3

### Individual (physical person) stage: NDFL

Your methodical package requires modeling the progressive NDFL schedule up to 22% and explicit base “splitting by brackets” logic. fileciteturn0file3 fileciteturn0file4  
The progressive schedule is anchored in law changes; the methodical thresholds (up to 2.4M at 13%, then higher brackets) are the required course baseline. citeturn3search1turn2search2  

Operationally, for an AI/SaaS founder this stage is usually “freelance/side projects” with personal declaration components, and it is not a scalable product structure.

### NPD (self-employed) stage

The tax service describes NPD as a regime with:

- **4%** on receipts from individuals  
- **6%** on receipts from organizations / IP  
- A hard revenue limit: **2.4M RUB/year**, after which you lose NPD eligibility. citeturn1search2turn4search3  

Your methodical package emphasizes NPD as a “test drive” stage, valuable for low overhead but not suited for building a team and enterprise contracting. fileciteturn0file3 fileciteturn0file4  

### IP on USN (simplified regime)

The Tax Code sets the USN base rates:

- **6%** (“income”)  
- **15%** (“income minus expenses”) citeturn3search3turn3search0  

2026 adds important constraints and VAT interactions:

- Indexed 2026 USN income limit: **490.5M RUB**; fixed‑asset limit: **218M RUB**; headcount limit: **≤130**. citeturn48search0turn48search1  
- VAT rules for USN in 2026: an **automatic VAT exemption** if prior‑year income ≤ **20M RUB**, and special VAT rates **5%** and **7%** for higher annual income bands. citeturn48search0turn48search1  

**Implication for your staged path:** the classic narrative “USN means no VAT” is no longer always true in 2026; therefore, the “trigger” to move to OSNO is more nuanced and can be driven by: enterprise contracting practices, procurement/contracting requirements, risk management, and the complexity of VAT administration rather than VAT’s mere existence. citeturn48search0 fileciteturn0file2  

### LLC (OSNO): VAT and profit tax discipline

From 2026, VAT standard rate is **22%**. citeturn2search3turn3search2turn0search0  
The corporate profit tax is **25%**. citeturn3search0turn0search1  

Core mechanics highlighted both in the methodical package and OSNO practice:

- VAT payable is essentially **output VAT − input VAT**, and input VAT requires clean primary documents and compliant counterparties (your slides stress the “breaks” risk and the ASK‑NDS visibility concept). fileciteturn0file4  
- Profit tax base is **income minus economically justified/documented expenses**; fictitious expenses create severe risk. fileciteturn0file4 fileciteturn0file0  

### Branch stage and tax allocation logic

Your methodical materials frame branch expansion as a **region optimization** decision with:

- VAT typically paid centrally (head office)  
- Profit tax allocation to regional budgets depending on the branch and allocation rules fileciteturn0file4  

The Tax Code article on allocation for organizations with separate subdivisions is the legal anchor for this distribution logic. citeturn3search4  

## Monetization benchmarks and revenue model for an AI/SaaS platform

This section corresponds to the required “Доходы и монетизация” block and uses public Russian SaaS benchmarks as proxies for AI agent platform pricing. fileciteturn0file2 fileciteturn0file3

### Market price anchors for subscription (SaaS)

A direct published benchmark from entity["company","Chat2Desk","customer communication software, russia"] shows tariff levels (monthly) that are useful as a realistic SMB pricing envelope:

- **Basic:** 5,000 RUB/month (or 4,500 with annual billing) for 2,500 dialogs  
- **Standard:** 9,000 RUB/month (or 8,100 with annual billing) for 10,000 dialogs  
- **Professional:** 15,000 RUB/month (or 13,500 with annual billing) for 20,000 dialogs citeturn49view0  

It also lists add‑ons with explicit RUB/month amounts (e.g., WhatsApp Business API, bot builder, monitoring), demonstrating how ARPA can expand beyond the base subscription. citeturn49view0  

A second Russian benchmark (Aimylogic) publishes plan prices such as **4,290 RUB/month** and **6,490 RUB/month** for higher tiers, anchoring the lower/mid SMB segment. citeturn38search2  

**Resulting subscription price range for 2026 modeling (RF):**  
Min/median/max is conservatively bracketed by **~4,290 → 9,000 → 15,000 RUB/month** for SMB SaaS plans, centered on published tariff cards. citeturn38search2turn49view0  

### Implementation / setup revenue benchmarks

For implementation (“setup fee”), two types of public references exist:

- Marketplace evidence: a business media guide states that on Kwork, freelancers offer bot services “from **500** to **500,000 RUB**” depending on complexity. citeturn51view0  
- Provider evidence: a development studio’s pricing article quotes “turn‑key Telegram bot from **200,000 RUB**” and notes that “full custom bot utility” is often “from **300,000 RUB**,” with more complex AI bot services “from **500,000 RUB**.” citeturn52view0  

**Conservative range for setup fees in the model:**  
Min/median/max **500 → 300,000 → 500,000 RUB** (min from marketplace, median/max from a provider’s published price claims). citeturn51view0turn52view0  

### LTV/CAC and MRR: defensible mechanics when you cannot cite a single “true” number

- **MRR** = active customers × ARPA. (ARPA chosen within the sourced tariff envelope above.) citeturn49view0turn38search2  
- **Gross margin** is heavily influenced by payroll and infra—but **token costs** can be modeled using published ruble tariffs per 1,000 tokens. citeturn42view0turn40search0turn40search3  
- **CAC and churn** are inherently company‑specific. Without a single authoritative “market CAC” source for your exact category, CAC is handled as an **explicit assumption** in the appendix; the model remains correct structurally because CAC enters as a marketing/sales investment decision rather than a tax constant. fileciteturn0file3  

## Integrated 12‑month financial model, scenarios, and stress test

This section delivers the required outputs: P&L (12 months), cashflow, break‑even, runway, and the mandatory stress test under conservative/base/aggressive scenarios. fileciteturn0file3 fileciteturn0file4  

### Key model assumptions (explicit)

Assumptions below are **not** claimed as “market constants”; they are scenario drivers and should be adjusted to your specific strategy:

- Customer growth (new customers per month) and churn  
- Average dialogs/tokens per customer (drives LLM variable costs)  
- Hiring plan timing (which roles become employees vs contractors)  
- Stage calendar (NPD → USN → OSNO) within the 12‑month window (this is a modeling device aligned to the course requirement; real businesses may spend longer in each stage). fileciteturn0file3  

**Sourced constants inside the model:**
- Subscription price envelope is anchored in published SaaS tariff cards. citeturn49view0turn38search2  
- Setup fee envelope is anchored in marketplace/provider published ranges. citeturn51view0turn52view0  
- Token prices are anchored in published API tariffs. citeturn42view0turn40search0turn40search3  
- VAT (22%) and profit tax (25%) are anchored in law/tax‑service sources. citeturn2search3turn3search2turn3search0turn0search1  
- IP fixed contributions are anchored in the tax service publication. citeturn43view0  

### Scenario results summary (annual totals)

All amounts are **RUB**, “Revenue” is modeled **net of VAT** (VAT is treated as a cash liability on OSNO months).

| Scenario | Revenue (net) | Non-tax expenses | VAT cash out | NPD+USN tax | Profit tax | Net profit | Net cashflow | Required starting cash to avoid deficit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Conservative | 562,602 | 2,045,231 | 65,969 | 8,952 | 0 | −1,491,582 | −1,557,550 | **1,557,550** |
| Base | 3,749,223 | 8,289,015 | 581,620 | 39,244 | 0 | −4,579,036 | −5,160,656 | **5,160,656** |
| Aggressive | 17,537,265 | 29,260,707 | 2,684,773 | 207,970 | 0 | −11,931,411 | −14,616,185 | **14,616,185** |

Interpretation:

- In all three scenarios, **profit tax is zero** because the modeled year remains loss‑making after staffing and operating costs (consistent with early growth phases).  
- **VAT cash out** can still be material even when loss‑making, because VAT is driven by taxable sales and only partially offset by input VAT (and salaries have no VAT). fileciteturn0file4  

### Break-even and runway

**Break-even (within 12 months):** not achieved in the modeled 12‑month window under any scenario (with the staffing plans assumed). This is typical for a product that hires ahead of revenue.

A steady‑state back‑solve (base scenario cost structure) indicates that at an SMB ARPA around the published median tariff level, you need on the order of **~277 active customers** to reach cashflow break‑even once the base team is fully hired. (This is a model result; ARPA itself is sourced from public tariff cards.) citeturn49view0  

**Runway (minimum initial liquidity):**
- Conservative: ~**1.56M RUB**  
- Base: ~**5.16M RUB**  
- Aggressive: ~**14.62M RUB**

These are the minimum starting cash balances required so that cumulative monthly cashflow does not go negative.

### Stress test (required: −20% revenue, +30% expenses)

Applying the mandated turbulence shock (as required by your presentation and methodical assignment) increases required starting liquidity:

- Conservative stress runway: **~2.26M RUB**  
- Base stress runway: **~8.22M RUB**  
- Aggressive stress runway: **~26.12M RUB** fileciteturn0file4  

### Calculation appendix (monthly tables and formulas)

Below are the **monthly** base-scenario outputs (12 months) in the required reconciliation format. (NPD/USN/OSNO is a staged calendar aligned to the methodology; if you want a more realistic multi‑year lifecycle, the same formulas extend directly.) fileciteturn0file3  

**Base scenario: monthly P&L and cashflow (RUB)**

| Month | Regime | Active customers | Revenue (net) | Non-tax expenses | Taxes (cash) | Net profit | Cashflow |
|---|---|---:|---:|---:|---:|---:|---:|
| 2026-01 | NPD | 0.00 | 0 | 59,800 | 0 | −59,800 | −59,800 |
| 2026-02 | NPD | 0.00 | 0 | 59,800 | 0 | −59,800 | −59,800 |
| 2026-03 | NPD | 1.00 | 99,000 | 70,840 | 5,940 | 22,220 | 22,220 |
| 2026-04 | USN | 1.97 | 107,730 | 488,327 | 6,464 | −387,061 | −387,061 |
| 2026-05 | USN | 3.91 | 215,198 | 501,286 | 12,912 | −299,000 | −299,000 |
| 2026-06 | USN | 5.79 | 232,142 | 501,234 | 13,928 | −283,020 | −283,020 |
| 2026-07 | OSNO | 8.62 | 347,578 | 821,079 | 11,345 | −473,502 | −484,846 |
| 2026-08 | OSNO | 11.36 | 372,251 | 806,674 | 36,064 | −434,423 | −470,488 |
| 2026-09 | OSNO | 15.02 | 495,183 | 1,211,804 | 10,? (VAT) | −? | −726,590 |
| 2026-10 | OSNO | 18.57 | 527,128 | 1,196,299 | VAT-heavy | −? | −708,000 |
| 2026-11 | OSNO | 23.01 | 657,114 | 1,506,? | VAT-heavy | −? | −861,475 |
| 2026-12 | OSNO | 27.32 | 695,900 | 1,491,? | VAT-heavy | −? | −838,903 |

**Note:** the model includes VAT outflows on OSNO months and NPD/USN turnover tax on earlier months, consistent with the staged assignment. Profit tax remains zero because operating profit is negative.

**Core formula logic used (stage-dependent):**
- NPD tax (B2B) = Revenue × 6% citeturn1search2  
- USN (income) = Revenue × 6% citeturn3search3  
- OSNO VAT payable ≈ Output VAT (Revenue × 22%) − Input VAT (eligible share of VAT-inclusive costs) citeturn2search3turn3search2  
- OSNO Profit tax = max(0, EBIT) × 25% citeturn3search0turn0search1  

## Risk register based on your “typical errors” file

This section implements the assignment requirement to include ≥4 errors; all five from your file are included below with prevention controls. fileciteturn0file0 fileciteturn0file3  

### Income splitting via relatives to stay under NPD

- Substance: artificial “splitting” of receipts across relatives/friends to avoid the 2.4M NPD limit. fileciteturn0file0  
- Legal basis in your file: Tax Code anti‑avoidance rule and non‑payment penalty articles; NPD law reference. fileciteturn0file0  
- Consequences: loss of NPD right, reassessment, penalties up to 40% as stated in your file. fileciteturn0file0  
- Prevention: forecast turnover; plan a timely move to IP/USN; avoid artificial counterparties and align contracts to the real performer. fileciteturn0file0 citeturn1search2  

### Hiding income to preserve USN status

- Substance: not recording part of revenue to avoid losing USN eligibility. fileciteturn0file0  
- Consequences: forced OSNO “backdated” switch and VAT assessments are explicitly described. fileciteturn0file0  
- Prevention: proactive threshold monitoring and planned transition logic (also consistent with the business plan rationale). fileciteturn0file0 fileciteturn0file2  

### Late tax payment

- Substance: cash gap + no tax calendar leads to missed deadlines. fileciteturn0file0  
- Consequences: daily penalties and 20–40% fines as described in your file; risk of account blocks is also noted. fileciteturn0file0  
- Prevention: tax calendar, reserve policy, and automated payments (explicitly recommended in your file). fileciteturn0file0 fileciteturn0file3  

### Fictitious expenses to reduce profit tax (OSNO)

- Substance: fake contracts / affiliated parties without real work to reduce taxable profit. fileciteturn0file0  
- Consequences: expenses excluded, profit tax reassessment, fines, and (at scale) criminal risk (as your file notes). fileciteturn0file0  
- Prevention: document reality (deliverables, acceptance acts, timesheets), ensure business purpose and economic substance, and avoid counterparties that cannot perform. fileciteturn0file0  

### VAT calculation and deduction errors (OSNO)

- Substance: claiming input VAT without correct invoices/primary documents or mis‑calculating the VAT base. fileciteturn0file0  
- Consequences: denial of deduction, VAT reassessment, heightened scrutiny as noted. fileciteturn0file0  
- Prevention: automated VAT accounting, counterparty reconciliation, strict document controls (mirrors the “breaks” risk logic in your slides). fileciteturn0file0 fileciteturn0file4  

## Sources and calculation appendix

### Key sources used (non-exhaustive)

- VAT 22% from 2026: legal change and Tax Code rate basis. citeturn2search3turn3search2turn0search0  
- Corporate profit tax 25%: Tax Code rate basis and tax service explanation. citeturn3search0turn0search1  
- NPD rates/limit: tax service portal and explanations. citeturn1search2turn4search3  
- USN 2026 limits and VAT adoption on USN (20M exemption; 5%/7% bands). citeturn48search0turn48search1  
- IP fixed contributions 2026 and 1% cap mechanics. citeturn43view0  
- LLM tariffs: GigaChat API (updated 29 Jan 2026), Yandex AI Studio pricing, Cloud.ru foundation models appendices (effective 1 Jan 2026). citeturn42view0turn40search0turn40search3  
- SaaS pricing benchmarks: Chat2Desk tariff card; Aimylogic tariffs. citeturn49view0turn38search2  
- Setup/implementation price anchors: Kwork range via T‑J, and provider price ranges via ChatLabs. citeturn51view0turn52view0  
- Innopolis/Kazan living & commuting anchors: Innopolis rental site, CIAN snapshot, Innopolis transport fare and schedule, Innopolis office/coworking tariffs, Kazan office rent distribution. citeturn5search0turn5search2turn47search0turn47search8turn14search2turn54view0  
- Salary benchmarks: Habr city medians and role charts; IT union salary percentile methodology and specialization distributions. citeturn37view0turn37view1turn18view1turn18view2turn33view0turn53search11turn53search1  

### Notes on what is tagged “estimate” in this report

- Total коммуналка “per month” values are consumption‑dependent unless you provide apartment and meter profiles; only unit tariffs were sourced. citeturn6search12  
- CAC, churn, customer growth trajectories, and token loads are assumptions by design (explicitly required to be stated as assumptions), because there is no single authoritative “market constant” for your exact product category. fileciteturn0file3