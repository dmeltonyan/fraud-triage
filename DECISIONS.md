# Decision log

One line per decision: what you chose and why. This becomes your interview prep and your case study.

| Date | Decision | Why |
| --- | --- | --- |
| 2026-10-04 | Split train, validation, and test by time, not randomly | A random split lets the model learn from future transactions, which inflates results |
| 2026-10-04 | Excluded gender, date of birth, and age from features | Protected attributes shouldn't drive financial decisions, and the model should work without them |
| 2026-10-04 | Use DuckDB for analysis in Weeks 1–2 and Supabase Postgres only for the Week 3 app | 1.85M rows would likely exceed Supabase's free tier; DuckDB is a local file built for fast analytical queries, while Postgres suits the app's small reads and writes |
| 2026-10-04 | Use the Kaggle Sparkov dataset (kartik2112/fraud-detection): 1,852,394 transactions, 9,651 fraud (0.521%), 2019-01-01 to 2020-12-31 | Only well-known public card-fraud dataset with real timestamps, card IDs, locations and merchant categories, which our features need; it is simulated, so results say nothing about real banks |
| 2026-10-04 | Combine Kaggle's two files and re-split by month ourselves | The given files have no validation set, split mid-day on 2020-06-21, and per-card history features need all of a card's past transactions in one table |
| 2026-10-04 | Train Jan 2019–Jun 2020, validate Jul–Sep 2020, test Oct–Dec 2020 (dates in config.yaml) | 18 months to learn from, 3 to tune and calibrate, 3 untouched; fixed before looking at patterns so the test months stay unseen. Test fraud rate is lower (Dec 2020 is 0.19%) because December volume doubles while fraud doesn't |
| 2026-10-04 | Feature pattern 1: amount. $500+ transactions are fraud 23% of the time vs 0.15% under $100 | Fraudsters go for large sums, so the amount, and especially the amount compared with that card's usual spend, should be the strongest signal |
| 2026-10-04 | Feature pattern 2: hour of day. 22:00–03:59 has 1.4–2.8% fraud vs about 0.1% the rest of the day | Fraud clusters at night, plausibly when cardholders are asleep and slower to notice; hour is cheap to compute and has no leakage risk |
| 2026-10-04 | Feature pattern 3: category. Online shopping, online misc and grocery POS run 1.3–1.7% fraud vs about 0.2% elsewhere | Card-not-present (online) purchases are easier to commit with stolen card details; category tells the model which merchants carry that risk |
