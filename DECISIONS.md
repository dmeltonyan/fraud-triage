# Decision log

One line per decision: what you chose and why. This becomes your interview prep and your case study.

| Date | Decision | Why |
| --- | --- | --- |
| | Split train, validation, and test by time, not randomly | A random split lets the model learn from future transactions, which inflates results |
| | Excluded gender, date of birth, and age from features | Protected attributes shouldn't drive financial decisions, and the model should work without them |
