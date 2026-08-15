# 📋 HH Goa 2026 · Task 2 Submission Kit

## 1 · Submission form
Fill https://forms.gle/MNvCjcv23Hn2Eeu58 **once**, only when final.

- GitHub repo: this repo
- Live link: deploy per `RAG-code/DEPLOY.md`, then paste the frontend URL
- Videos (below)

## 2 · Video 1 — Team/process (90 s)
Shows **how** you built it, not the product. Ideas:

- Opening slate: team + task (#RAGInGoa)
- Clip of the planning board / README requirements checklist (6 requirements)
- 10–20 s of `ingest_msmarco.py` building the 4-language index
- Clip of `benchmark.py` printing the P50/P70/P100 report
- Clip of `tests.py` passing (31 checks)
- Short screen-record of the team iterating on latency numbers
- Ending card: repo link + #RAGInGoa

## 3 · Video 2 — Demo (end-to-end)
Shows the product working. Suggested script (≤ 60 s of action):

1. Open the live app. Show the 4-language selector (Auto/हिन्दी/English/ગુજરાતી/मराठी).
2. **Hindi** — speak: "क्यूबा की मुद्रा क्या है?" → transcript → answer.
3. **English** — type: "What is the currency of Cuba?" → answer.
4. **Gujarati** — type: "હેરિસન ફોર્ડના દીકરા કોણ છે?"
5. **Marathi** — type: "मोलासेस पूरात किती लोक मरण पावले?"
6. Show the **latency panel** (live P50/P70/P100 + per-language) and a
   retrieval-only p50 well under 200 ms.
7. Show a **guardrail**: ask something off-corpus (e.g. "who won the 2026 FIFA
   World Cup?") → refusal. Then speak in **Tamil** → refused ("only
   hi/en/gu/mr").
8. Ending card: repo + live link + #RAGInGoa.

## 4 · Mandatory promotion
Both videos must be uploaded to **Instagram, X and LinkedIn by every member**.
At least 1 Instagram account public. Every post includes: **#RAGInGoa**.

## 5 · Deadline
August 22, 2026, 11:59 PM. No resubmissions — submit only when final.

## 6 · Script for the demo Q&A (accurate answers in corpus)

| Language | Query | Expected answer (grounded) |
|---|---|---|
| hi | क्यूबा की मुद्रा क्या है? | क्यूबा की मुद्रा क्यूबाई पेसो है (gold answer from corpus) |
| en | What is the currency of Cuba? | The Cuban peso is the currency of Cuba |
| gu | હેરિસન ફોર્ડના દીકરા કોણ છે? | (gold answer from corpus) |
| mr | मोलासेस पूरात किती लोक मरण पावले? | (gold answer from corpus) |