// Headline numbers for the overview page, read at build time from copies of
// reports/metrics.json and reports/policy_results.json (in web/results/). Built into
// the site, so the overview never waits for the API to wake up. After retraining,
// copy the two files again (see DEPLOY.md).
import metrics from "@/results/metrics.json";
import results from "@/results/policy_results.json";

const sets = Object.values(metrics.sets);
const ours = results.default.cost_based;
const threshold = results.default.threshold;

export const FACTS = {
  transactions: sets.reduce((sum, s) => sum + s.rows, 0),
  frauds: sets.reduce((sum, s) => sum + s.fraud, 0),
  testMonths: results.test_months,
  reviewBudget: results.default_budget,
  reviewShare: metrics.review_share,
  recallAtTop: metrics.models.lightgbm.test.recall_at_top,
  prAuc: metrics.models.lightgbm.test.pr_auc,
  ourTotalCost: ours.total_cost,
  thresholdTotalCost: threshold.total_cost,
  costReduction: 1 - ours.total_cost / threshold.total_cost,
};

export const REPO_URL = "https://github.com/dmeltonyan/fraud-triage";

// A case from the demo that reads clearly: $745.88 at 03:48, 21 times the card's
// typical purchase, sent to review, and really fraud.
export const EXAMPLE_CASE_ID = "808d112f86a9385ce6243430dbb22dff";
