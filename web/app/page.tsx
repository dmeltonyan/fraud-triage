import Link from "next/link";
import { wholeMoney } from "@/lib/format";
import { DATASET, EXAMPLE_CASE_ID, FACTS, REPO_URL, STACK } from "@/lib/project-facts";
import ActionBadge from "./action-badge";
import WarmUp from "./warm-up";

const STEPS = [
  {
    title: "A card transaction arrives",
    body: "Amount, merchant category, time of day, and the card's recent history: how often it was used in the last hour and day, and how this amount compares with its usual spend.",
  },
  {
    title: "The model scores it",
    body: "A LightGBM model, trained only on earlier months, gives a calibrated fraud probability: a score of 30% means about 3 in 10 such transactions really are fraud.",
  },
  {
    title: "The policy decides",
    body: "It compares the expected dollar cost of each action and picks the cheapest. Analysts can only check 30 cases a day, so review slots go where they save the most money.",
  },
  {
    title: "An analyst reviews",
    body: "That's you. Open a case, read why it was flagged, and make the call. The app then reveals whether it was really fraud.",
  },
];

export default function OverviewPage() {
  const stats = [
    { value: `${(FACTS.transactions / 1e6).toFixed(2)}M`, label: "card transactions over two years" },
    {
      value: `${Math.round(FACTS.recallAtTop * 100)}%`,
      label: `of fraud caught by reviewing just ${Math.round(FACTS.reviewShare * 100)}% of transactions`,
    },
    {
      value: `${Math.round(FACTS.costReduction * 100)}%`,
      label: "lower total fraud cost than reviewing the highest-scoring cases",
    },
    {
      value: `${FACTS.testMonths.length} months`,
      label: "held out for the final test; every split and feature looks only at the past",
    },
  ];

  return (
    <div className="space-y-14">
      <WarmUp />

      <section>
        <p className="text-sm font-semibold uppercase tracking-wide text-accent">Machine learning · decision-making</p>
        <h1 className="mt-2 max-w-3xl text-3xl font-semibold leading-tight sm:text-4xl">
          A fraud model says how likely fraud is. This system decides what to do about it.
        </h1>
        <div className="mt-4 max-w-3xl space-y-2 text-sm">
          <p>
            <span className="font-semibold">Data:</span>{" "}
            <a href={DATASET.url} className="text-accent hover:underline">
              {DATASET.name}
            </a>{" "}
            <span className="text-muted">
              · {(FACTS.transactions / 1e6).toFixed(2)}M card transactions, January 2019 to December 2020, generated
              with the Sparkov simulator.
            </span>
          </p>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 font-semibold">Built with:</span>
            {STACK.map((tool) => (
              <span key={tool} className="rounded-md border border-line bg-surface px-2 py-0.5 text-xs">
                {tool}
              </span>
            ))}
          </div>
          <p className="text-muted">Deployed on Render and Vercel.</p>
        </div>
        <p className="mt-5 max-w-3xl text-lg text-muted">
          Each card transaction is scored by a machine-learning model. A cost-based policy then picks one of three
          actions by comparing expected dollar losses, with only a limited number of analyst reviews per day:
        </p>
        <ul className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
          <li className="flex items-center gap-2">
            <ActionBadge action="approve" /> <span className="text-sm text-muted">let it through</span>
          </li>
          <li className="flex items-center gap-2">
            <ActionBadge action="review" /> <span className="text-sm text-muted">send to an analyst</span>
          </li>
          <li className="flex items-center gap-2">
            <ActionBadge action="block" /> <span className="text-sm text-muted">decline it</span>
          </li>
        </ul>
        <p className="mt-5 max-w-3xl text-lg">
          On three held-out months, it cost <strong>{wholeMoney(FACTS.ourTotalCost)}</strong> against{" "}
          <strong>{wholeMoney(FACTS.thresholdTotalCost)}</strong> for the usual approach of reviewing the
          highest-scoring cases: <strong>{Math.round(FACTS.costReduction * 100)}% less</strong>.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href={`/case/${EXAMPLE_CASE_ID}`}
            className="rounded-md bg-accent px-5 py-3 font-medium text-white hover:opacity-90"
          >
            Start with an example case
          </Link>
          <Link href="/queue" className="rounded-md border border-accent px-5 py-3 font-medium text-accent">
            Open the review queue
          </Link>
          <Link href="/results" className="rounded-md px-5 py-3 font-medium text-accent hover:underline">
            See the results →
          </Link>
        </div>
      </section>

      <section aria-labelledby="numbers">
        <h2 id="numbers" className="sr-only">
          Key numbers
        </h2>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="flex flex-col rounded-lg border border-line bg-surface p-4">
              <dt className="text-sm text-muted">{s.label}</dt>
              <dd className="order-first text-3xl font-semibold text-accent">{s.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section aria-labelledby="how">
        <h2 id="how" className="text-2xl font-semibold">
          How it works
        </h2>
        <ol className="mt-4 grid gap-4 md:grid-cols-4">
          {STEPS.map((step, i) => (
            <li key={step.title} className="rounded-lg border border-line p-4">
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-light font-semibold text-accent">
                {i + 1}
              </span>
              <h3 className="mt-3 font-semibold">{step.title}</h3>
              <p className="mt-1 text-sm text-muted">{step.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="why" className="max-w-3xl">
        <h2 id="why" className="text-2xl font-semibold">
          Why this matters
        </h2>
        <p className="mt-3">
          Fraud models are easy to train and hard to act on. Fraud is rare (about 1 in 190 transactions here), so a
          model that never flags anything is 99.5% accurate and useless. And analysts can only check a handful of cases
          a day, so the real question isn&apos;t &ldquo;is this fraud?&rdquo; but &ldquo;which cases deserve a
          person&apos;s time?&rdquo;
        </p>
        <p className="mt-3">
          Ranking by probability alone wastes review slots on small purchases. Ranking by expected dollars, and
          blocking near-certain fraud outright, catches more of the money with fewer reviews.
        </p>
        <p className="mt-3 text-sm text-muted">
          The model scores transactions offline; this demo serves the precomputed results so it can run on free
          hosting. Full design decisions, tests and limitations are in the{" "}
          <a href={REPO_URL} className="text-accent hover:underline">
            GitHub repository
          </a>
          .
        </p>
      </section>
    </div>
  );
}
