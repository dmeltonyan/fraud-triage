# Fraud Triage: instructions for AI coding assistants

Read this file and ROADMAP.md at the start of every session.

## What this project is

A fraud detection system with a human review queue. A model scores each card transaction, a decision policy turns that score into an action (approve, send to review, or block) by comparing expected costs under a daily review budget, and analysts handle the uncertain cases in a web app.

## Who you're working with

I'm a computer science student with limited professional development experience. I will be interviewed about every line of this project, so I need to understand it, not just have it work.

## Rules

1. **Plan before coding.** For each task, explain in plain English which files you'll create or change and why. Wait for my OK before writing code.
2. **Small steps.** One ROADMAP step at a time. Never change more than a few files at once.
3. **Explain every change.** After writing code, walk me through it file by file in plain English, then give me the one command to run to check it works.
4. **Explain errors before fixing them.** Tell me what the error means and why it happened, then fix it.
5. **Ask before adding dependencies.** Tell me what the package does and why we need it.
6. **No secrets in code.** Database URLs and API keys live in `.env`, which is never committed. Use `.env.example` to show which variables exist.
7. **Never commit data.** Raw data lives in `data/`, which is gitignored. Provide a script that downloads or loads it.
8. **Time-based splits only.** Train on earlier months, validate on the next, test on the last. Never use a random train/test split.
9. **Never use gender, date of birth, or age as model features**, even though the dataset includes them.
10. **No hidden numbers.** Every cost assumption and threshold lives in `config.yaml` with a comment saying it's an assumption.
11. **Test the core logic.** Feature functions and the decision policy get pytest tests.
12. **End of session.** Draft one line for DECISIONS.md describing what we decided and why, then ask me 5 interview-style questions about today's work. Don't reveal answers until I try.

## Stack

- Python 3.11, pandas, scikit-learn, LightGBM, SHAP
- DuckDB (a local file database at `data/fraud.duckdb`) for all analysis and feature engineering in Weeks 1 and 2
- PostgreSQL on Supabase, accessed with SQLAlchemy, only in Week 3 for the review app and a small demo sample
- FastAPI for the scoring and review API
- pytest for tests
- Next.js with TypeScript for the review app (week 3), in `web/`

## Layout

```
fraud-triage/
  data/            raw CSVs and the DuckDB file fraud.duckdb (gitignored)
  src/             Python package: loading, features, model, policy, api
  notebooks/       exploration only, never imported by src/
  tests/           pytest tests
  web/             Next.js review app (week 3)
  config.yaml      costs, thresholds, review budget
  DECISIONS.md     decision log for interview prep
  ROADMAP.md       the plan
```
