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
- [ ] **5. Time-based split and baseline.** Train, validate, and test by month. Logistic regression baseline.
  Done when: precision-recall AUC prints for the test months.
- [ ] **6. LightGBM.** Train and compare with the baseline.
  Done when: both scores are recorded in DECISIONS.md.

## Week 2: decisions and API

- [ ] **7. Calibration.** Calibrate probabilities on the validation months and plot a reliability curve.
  Done when: the plot is saved and predicted probabilities line up with actual fraud rates.
- [ ] **8. Cost model.** Missed fraud, review cost, and false-decline cost in `config.yaml`, each marked as an assumption.
  Done when: changing a value in the config changes the results without touching code.
- [ ] **9. Decision policy.** Expected cost of approve, review, and block per transaction; pick the cheapest; enforce a daily review budget ranked by expected loss prevented.
  Done when: tests in `tests/test_policy.py` pass.
- [ ] **10. Policy comparison.** Dollars lost on the test months for approve-everything, a fixed score threshold, and the cost-based policy.
  Done when: one chart compares all three and you can state the headline number.
- [ ] **11. Explanations.** Top three SHAP features per transaction.
  Done when: any transaction's reasons can be printed in plain words.
- [ ] **12. API.** FastAPI with `POST /score`, `GET /queue`, and `POST /review/{id}`.
  Done when: each endpoint works from the auto-generated `/docs` page.

## Week 3: review app and deployment

- [ ] **13. Review queue.** Next.js page listing cases by expected loss, a detail view with amount, merchant, score, and reasons, and Confirm fraud / Mark legitimate buttons.
  Done when: reviewing a case in the browser saves the decision to Postgres.
- [ ] **14. Monitoring page.** Weekly score distribution and fraud caught across the test months.
  Done when: the page loads with real numbers.
- [ ] **15. Deploy.** Load a pre-scored sample of about 20,000 test-period transactions into Supabase, deploy the API (Render or Railway) and the web app (Vercel), and add a banner saying the data is simulated.
  Done when: the live link works on your phone.

## Week 4: demos and publishing

- [ ] **16. README.** Headline result first, then a GIF, the policy chart, architecture, how to run, and assumptions and limitations.
- [ ] **17. Video.** A two-minute walkthrough, uploaded unlisted.
- [ ] **18. Publish.** Pin the repo, add topics, add it to the portfolio site, and rehearse the two-minute and ten-minute explanations out loud.

## Cut list if you fall behind

Cut 14 first, then 11. Never cut 5, 9, or 10.
