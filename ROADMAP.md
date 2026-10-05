# Fraud Triage roadmap

One step per session. Check the box only when "done when" is true.

## Week 1: data and model

- [x] **1. Project setup.** Create the folder layout, a virtual environment, `requirements.txt`, `.gitignore`, `.env.example`, and `config.yaml`.
  Done when: `python -c "import pandas, lightgbm"` runs without errors and the first commit is on GitHub.
- [x] **2. Load the data.** Write `src/load.py` to combine the two Kaggle CSVs (`fraudTrain.csv` and `fraudTest.csv`) into one `transactions` table in a local DuckDB file at `data/fraud.duckdb`.
  Done when: a SQL query against DuckDB returns the transaction count and the number of fraud cases.
- [x] **3. Explore.** In a notebook: fraud rate, fraud by category and hour, amount distributions, date range.
  Done when: you can state the fraud rate and the date range from memory.
- [x] **4. Features.** Transactions per card in the last hour and last day, amount compared with that card's usual amount, hour of day, home-to-merchant distance, category. Historical features use only past data. No gender, date of birth, or age.
  Done when: tests in `tests/test_features.py` pass, including one proving no feature uses future data.
- [x] **5. Time-based split and baseline.** Train, validate, and test by month. Logistic regression baseline.
  Done when: precision-recall AUC prints for the test months.
- [x] **6. LightGBM.** Train and compare with the baseline.
  Done when: both scores are recorded in DECISIONS.md.

## Week 2: decisions and API

- [x] **7. Calibration.** Calibrate probabilities on the validation months and plot a reliability curve.
  Done when: the plot is saved and predicted probabilities line up with actual fraud rates.
- [x] **8. Cost model.** Missed fraud, review cost, and false-decline cost in `config.yaml`, each marked as an assumption.
  Done when: changing a value in the config changes the results without touching code.
- [x] **9. Decision policy.** Expected cost of approve, review, and block per transaction; pick the cheapest; enforce a daily review budget ranked by expected loss prevented.
  Done when: tests in `tests/test_policy.py` pass.
- [x] **10. Policy comparison.** Dollars lost on the test months for approve-everything, a fixed score threshold, and the cost-based policy.
  Done when: one chart compares all three and you can state the headline number.
- [x] **11. Explanations.** Top three SHAP features per transaction.
  Done when: any transaction's reasons can be printed in plain words.
- [x] **12. API.** FastAPI with `POST /score`, `GET /queue`, and `POST /review/{id}`.
  Done when: each endpoint works from the auto-generated `/docs` page.

## Week 3: review app and deployment

Design: scoring runs offline (batch scoring). The deployed demo serves precomputed results from Supabase Postgres, so the production API never loads LightGBM or SHAP and stays small enough for free hosting.

- [x] **13. Demo data and production API.** `sql/schema.sql` and `src/export_demo.py` load a pre-scored sample of about 20,000 test-period transactions (every review and block case plus a random sample of approvals, with no personal fields) into Supabase. The API gains a `postgres` mode that serves those results and records reviews, with its own small `requirements-api.txt`.
  Done when: the API in postgres mode answers every endpoint from Supabase.
- [ ] **14. Review app.** Next.js in `web/`: a review queue by expected loss, a case page with reasons and the expected cost of each action, Confirm fraud / Mark legitimate buttons, a results page with the policy comparison, and a banner saying the data is simulated.
  Done when: reviewing a case in the browser saves the decision to Supabase.
- [ ] **15. Deploy.** The API on Render and the web app on Vercel, following `DEPLOY.md`.
  Done when: the live link works on your phone.

## Week 4: demos and publishing

- [ ] **16. README.** Headline result first, then a GIF, the policy chart, architecture, how to run, and assumptions and limitations.
- [ ] **17. Video.** A two-minute walkthrough, uploaded unlisted.
- [ ] **18. Publish.** Pin the repo, add topics, add it to the portfolio site, and rehearse the two-minute and ten-minute explanations out loud.

## Cut list if you fall behind

Cut the app's automated smoke tests first (check by hand instead), then the results page (link the README's results instead), then 11. Never cut 5, 9, or 10.
