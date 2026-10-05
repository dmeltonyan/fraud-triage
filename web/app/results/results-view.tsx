"use client"; // loads the results from the API in the browser

import Image from "next/image";
import type { PolicyName, Stats } from "@/lib/api";
import { money, wholeMoney } from "@/lib/format";
import { errorMessage, useApiGet } from "@/lib/use-api";
import { LoadError, Loading } from "../status";

const POLICIES: { name: PolicyName; label: string; description: string }[] = [
  { name: "approve_all", label: "Approve everything", description: "No fraud checks at all." },
  {
    name: "threshold",
    label: "Highest probability",
    description: "Each day, review the most likely frauds up to the budget; approve the rest.",
  },
  {
    name: "cost_review_only",
    label: "Highest expected dollars",
    description: "Same budget, but rank by probability × amount; no blocking.",
  },
  {
    name: "cost_based",
    label: "Cost-based (this project)",
    description: "Cheapest of approve, review or block; review slots go where they save the most.",
  },
];

export default function ResultsView() {
  const { state, slow, retry } = useApiGet<Stats>("/stats");
  if (state.status === "loading") return <Loading what="results" slow={slow} />;
  if (state.status === "error") {
    return <LoadError message={`Couldn't load the results. ${errorMessage(state.error)}`} onRetry={retry} />;
  }

  const s = state.data;
  const ours = s.default.cost_based;
  const baseline = s.default.threshold;
  const saving = 1 - ours.total_cost / baseline.total_cost;

  return (
    <section className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Results</h1>
        <p className="mt-3 text-lg">
          On three held-out months of simulated card transactions, with analysts limited to {s.default_budget} reviews
          a day, the cost-based policy cost {wholeMoney(ours.total_cost)} in total against {wholeMoney(baseline.total_cost)} for
          reviewing the highest-probability cases: {Math.round(saving * 100)}% less.
        </p>
        <p className="mt-2 text-sm text-muted">
          Test months {s.test_months[0]} to {s.test_months[s.test_months.length - 1]}:{" "}
          {s.transactions.toLocaleString()} transactions, {s.frauds.toLocaleString()} frauds worth{" "}
          {money(s.fraud_dollars)}. Total cost = fraud lost + reviews × review cost + legitimate customers declined ×
          decline cost.
        </p>
      </div>

      <div>
        <h2 className="text-lg font-semibold">The policies at {s.default_budget} reviews a day</h2>
        {/* Narrow screens (under 640 px): one card per policy, total cost first */}
        <ul className="mt-3 space-y-3 sm:hidden">
          {POLICIES.map(({ name, label, description }) => {
            const o = s.default[name];
            return (
              <li
                key={name}
                className={`rounded-md border border-line p-4 ${name === "cost_based" ? "bg-accent-light" : ""}`}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium">{label}</span>
                  <span className="text-lg font-semibold">{wholeMoney(o.total_cost)}</span>
                </div>
                <p className="mt-1 text-xs text-muted">{description}</p>
                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  <dt className="text-muted">Fraud lost</dt>
                  <dd className="text-right">{wholeMoney(o.fraud_dollars_lost)}</dd>
                  <dt className="text-muted">Fraud caught</dt>
                  <dd className="text-right">{wholeMoney(o.fraud_dollars_caught)}</dd>
                  <dt className="text-muted">Reviews</dt>
                  <dd className="text-right">{o.reviews.toLocaleString()}</dd>
                  <dt className="text-muted">Legitimate declined</dt>
                  <dd className="text-right">{o.legit_declined.toLocaleString()}</dd>
                </dl>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-xs text-muted sm:hidden">Large figure = total cost.</p>

        {/* Wider screens: a table */}
        <div className="mt-3 hidden sm:block">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-line text-muted">
              <tr>
                <th className="py-2 font-medium">Policy</th>
                <th className="py-2 text-right font-medium">Fraud lost</th>
                <th className="py-2 text-right font-medium">Fraud caught</th>
                <th className="py-2 text-right font-medium">Reviews</th>
                <th className="py-2 text-right font-medium">Legitimate declined</th>
                <th className="py-2 text-right font-medium">Total cost</th>
              </tr>
            </thead>
            <tbody>
              {POLICIES.map(({ name, label, description }) => {
                const o = s.default[name];
                return (
                  <tr key={name} className={`border-b border-line ${name === "cost_based" ? "bg-accent-light" : ""}`}>
                    <td className="py-2 pr-4">
                      <div className="font-medium">{label}</div>
                      <div className="text-xs text-muted">{description}</div>
                    </td>
                    <td className="py-2 text-right">{money(o.fraud_dollars_lost)}</td>
                    <td className="py-2 text-right">{money(o.fraud_dollars_caught)}</td>
                    <td className="py-2 text-right">{o.reviews.toLocaleString()}</td>
                    <td className="py-2 text-right">{o.legit_declined.toLocaleString()}</td>
                    <td className="py-2 text-right font-semibold">{money(o.total_cost)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <figure>
        <h2 className="text-lg font-semibold">Fraud lost as the review budget changes</h2>
        <Image
          src="/figures/budget_curve.png"
          alt="Line chart of fraud dollars lost against the daily review budget from 5 to 60. Highest-probability ranking loses the most at small budgets, ranking by expected dollars loses less, and the cost-based policy with blocking stays near $5,000 at every budget."
          width={836}
          height={563}
          className="mt-3 h-auto w-full max-w-3xl"
        />
        <figcaption className="mt-2 text-sm text-muted">
          With a small budget, choosing reviews by expected dollars beats choosing by probability; blocking likely fraud
          keeps losses low without using review slots.
        </figcaption>
      </figure>

      <figure>
        <h2 className="text-lg font-semibold">Are the probabilities honest?</h2>
        <Image
          src="/figures/calibration.png"
          alt="Reliability chart on the test months: after calibration, predicted fraud probabilities follow the diagonal of actual fraud rates; the raw model was overconfident."
          width={657}
          height={658}
          className="mt-3 h-auto w-full max-w-md"
        />
        <figcaption className="mt-2 text-sm text-muted">
          The policy multiplies probability by amount, so probabilities must match real fraud rates. Calibration fixes
          the raw model, which was trained with fraud weighted 13 times and was overconfident.
        </figcaption>
      </figure>

      <div>
        <h2 className="text-lg font-semibold">Assumptions</h2>
        <p className="mt-1 text-sm text-muted">Every number below is an assumption, set in config.yaml.</p>
        <ul className="mt-3 list-disc space-y-1 pl-5">
          <li>One analyst review costs {money(s.costs.review_cost_usd)}.</li>
          <li>Blocking a legitimate customer costs {money(s.costs.false_decline_cost_usd)}.</li>
          <li>Analysts can review {s.default_budget} cases a day.</li>
          <li>An approved fraud loses its whole amount; there is no chargeback or recovery.</li>
          <li>An analyst always catches fraud and always approves a legitimate transaction.</li>
          <li>Blocking a fraud costs nothing.</li>
          <li>
            The daily review budget is applied with the whole day in view, as if analysts worked through the queue at
            the end of the day.
          </li>
          <li>The data is simulated (Sparkov), so these results say nothing about real banks.</li>
        </ul>
      </div>
    </section>
  );
}
