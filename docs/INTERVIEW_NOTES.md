# Interview notes: cfpb-complaint-signals

A plain-English walkthrough so you can explain this project with confidence.

## The 30-second pitch

"I took about 800,000 CFPB consumer complaints for 10 big banks and fintechs, covering 2018 to mid-2026. I built a pipeline that cleans the free-text narratives, finds the main complaint themes with TF-IDF and NMF topic modeling, and rolls everything up into quarterly signals in DuckDB SQL. Then I tested those signals against stock returns. The most useful finding is about data quality: the biggest 'spikes', like Cash App's 36x jump in early 2025, were mostly copy-paste campaigns that started the week a CFPB enforcement action hit. If you trade raw complaint counts, you're trading those campaigns. Complaint growth itself wasn't a bearish signal, because it mostly tracks customer growth."

## How it works, step by step

1. **Get the data.** The CFPB stopped publishing narratives on the live site on August 14, 2026, but it put the full history in a FOIA archive of zipped CSVs. I download exports #2–#21 (May 2018 to Aug 2026, about 1.3 GB) and stream them in 250k-row chunks, keeping only the 10 companies. That leaves 838,347 rows.
2. **Validate.** I check my archive counts against the live CFPB API, which still serves counts, for three banks across three years. All 9 match exactly. Always reconcile against an independent source before analysis.
3. **Clean the text.** I lowercase, remove the CFPB's redaction tokens (`XXXX`), dollar placeholders and URLs, and **remove brand names**. Without that last step, the topic model learns a "PayPal topic" and a "Cash App topic", which tells you nothing new.
4. **TF-IDF.** Each narrative becomes a vector of word and two-word-phrase weights. A term gets more weight if it is frequent in *this* complaint but rare across all complaints. Very rare terms (fewer than 25 docs) and very common ones (more than 40% of docs) are dropped.
5. **NMF topic model.** Non-negative matrix factorization splits the document-term matrix into *documents × topics* and *topics × terms*. Because everything is non-negative, each topic is an additive bundle of words, which makes it easy to read. I fit 12 topics on a 111k-narrative sample **stratified by company and quarter**, so no single bank or quarter dominates, and then score all 356k narratives.
6. **Label the topics.** I read each topic's top terms and its most representative complaints, then named them: "Deposits, transfers & frozen funds", "Late payments & fees", "Identity theft", and so on. Three topics turned out to be **templates**, with near-identical text pasted by many people.
7. **Flag templates.** If the first 120 cleaned characters of a narrative are shared by 10 or more narratives, it is flagged. That is 9.8% of all narratives, and 77% of Block's 2025 Q1 narratives.
8. **SQL signals.** DuckDB computes quarterly complaint counts, untimely-response share, product mix, YoY growth (`LAG(..., 4)`), topic shares and template shares. It joins them to quarterly returns minus XLF, with `LEAD` for next-quarter and quarter-after-next returns.
9. **Test.** Each quarter I rank the 10 names by a signal and check (a) the rank correlation with next-quarter excess return and (b) a long-3/short-3 spread. Ranking within a quarter removes market-wide moves.

## Results to quote

* Block: 1,014 complaints in 2024 Q4, then 36,929 in 2025 Q1. About 90 a week became 21,933 in the week of Jan 13, 2025 (the CFPB order was Jan 16). 77% of that quarter's narratives were templates.
* Capital One: 5,048 complaints the same week (22% template), concentrated in savings accounts. The CFPB sued over 360 Savings rates on Jan 14, 2025.
* Topic fingerprints for 2024-2025: PayPal is 25% frozen funds and 25% disputes; Amex is 22% card/limits; Synchrony has the most late-fee complaints (15%); Ally's top topic is auto and mortgage loans (20%).
* Signal test: complaint growth vs next-quarter excess return, within-quarter ρ = +0.10 (p = 0.10). The long-slow/short-fast spread averaged −3.5% per quarter (p = 0.16), so it is **not** a bearish signal. Untimely-response share: ρ = −0.14 (p = 0.015), but it is fragile because only 3 firms have meaningful non-zero values.

## Likely interview questions and good answers

**Why NMF and not LDA or BERTopic?**
NMF on TF-IDF is fast, deterministic with a seed, and gives sharp, readable topics on short texts, which complaints are. LDA assumes word counts, works better on longer documents, and is slower to tune. BERTopic (embeddings plus clustering) would catch paraphrases better and is a natural upgrade, but it is heavier and harder to explain. For a first pass at an alt-data source, I want something transparent.

**How did you choose 12 topics?**
I traded off readability against redundancy. Fewer topics merged fees with disputes; more topics split templates into near-duplicates. With more time, I'd compare coherence scores across k = 8 to 20 and check stability across random seeds.

**Why remove company names?**
Otherwise the model learns which company a complaint is about. Then "PayPal's topic mix" just says "PayPal complaints mention PayPal". Removing brands forces the topics to describe the problem.

**Is complaint volume a good alt-data signal?**
On its own, not really. It grows with customers, product launches (like card portfolio growth) and CFPB visibility. It also has campaign spikes. You'd want to normalize per customer or per dollar of balances from 10-Q or Y-9C filings, remove templates, and look at *changes in mix*. For example, a rising share of fraud or frozen-funds complaints at a payments company is more informative than total volume.

**What's the look-ahead risk?**
Complaints are published after the company responds or after 15 days, so a quarter's count isn't fully known on the last day of the quarter. That's why I also test the quarter after next. In production I'd store daily snapshots and only use what was visible as of each date. The CFPB's 2026 policy change also means the narrative history is now frozen, so a live version would rely on structured fields (product, issue, timeliness) going forward.

**How would you make this useful to a PM covering financials?**
I'd set up a weekly monitor per covered name with volume vs its own history, template-adjusted. I'd add topic-share shifts with example complaints attached, alerts when untimely responses jump (a sign of operational stress), and a note when spikes line up with enforcement actions or outages. The analyst reads the examples. The model's job is to point them to what changed.

**What would you do with more time?**
Normalize by accounts or balances. Add more issuers (regional banks, BNPL) for statistical power. Use event studies around enforcement actions instead of quarterly returns. Run sentiment or severity scoring on narratives. And de-duplicate templates more robustly with MinHash or embedding similarity.

**What's the data licensing situation?**
The CFPB data is public domain (CC0) and the narratives are already scrubbed of personal information. That is the kind of question Compliance would sign off on before any production use.

## Numbers you should know cold

10 companies · 797k complaints (2018 Q3–2026 Q2) · 356k narratives · 12 topics · 9.8% templates · Block 2025 Q1 = 36,929 complaints, 77% template · archive matches live API in 9/9 checks.
