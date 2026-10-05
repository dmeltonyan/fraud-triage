"use client"; // loads the case and handles the decision buttons in the browser

import Link from "next/link";
import { useState } from "react";
import { ApiError, apiPost, type Action, type ReviewResult, type TransactionDetail } from "@/lib/api";
import { categoryName, dateTime, money, percent } from "@/lib/format";
import { errorMessage, useApiGet } from "@/lib/use-api";
import ActionBadge, { ACTION_STYLES } from "../../action-badge";
import { LoadError, Loading } from "../../status";

const ACTION_ORDER: Action[] = ["approve", "review", "block"];

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-line p-4">
      <h2 className="flex items-center gap-2 font-semibold">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-light text-sm text-accent">
          {n}
        </span>
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export default function CaseView({ id }: { id: string }) {
  const { state, slow, retry } = useApiGet<TransactionDetail>(`/transactions/${id}`);

  if (state.status === "loading") return <Loading what="the case" slow={slow} />;
  if (state.status === "error") {
    const missing = state.error instanceof ApiError && (state.error.status === 404 || state.error.status === 422);
    if (missing) {
      return (
        <section>
          <h1 className="text-2xl font-semibold">Case not found</h1>
          <p className="mt-2 text-muted">There is no case with this ID in the demo.</p>
          <Link href="/queue" className="mt-4 inline-block text-accent hover:underline">
            ← Back to the queue
          </Link>
        </section>
      );
    }
    return <LoadError message={`Couldn't load the case. ${errorMessage(state.error)}`} onRetry={retry} />;
  }

  const c = state.data;
  const day = c.timestamp.slice(0, 10);
  return (
    <div className="space-y-4">
      <Link href={`/queue?date=${day}`} className="text-sm text-accent hover:underline">
        ← Back to the queue for {day}
      </Link>
      <h1 className="text-2xl font-semibold">Case review</h1>

      <Step n={1} title="The transaction">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-lg font-semibold">{c.merchant}</div>
            <p className="text-muted">
              {categoryName(c.category)} · {c.city}, {c.state} · {dateTime(c.timestamp)}
            </p>
          </div>
          <div className="sm:text-right">
            <div className="text-2xl font-semibold">{money(c.amount)}</div>
            <div className="text-sm text-muted">Fraud probability {percent(c.fraud_probability)}</div>
          </div>
        </div>
      </Step>

      <Step n={2} title="Why the model flagged it">
        <p className="text-sm text-muted">The three things that moved this transaction&apos;s fraud score the most:</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5">
          {c.reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ol>
      </Step>

      <Step n={3} title="What the policy decided">
        <CostBars costs={c.expected_costs} action={c.action} />
      </Step>

      <Step n={4} title="Your call">
        <Decision id={c.transaction_id} />
      </Step>
    </div>
  );
}

function CostBars({ costs, action }: { costs: TransactionDetail["expected_costs"]; action: Action }) {
  const largest = Math.max(...ACTION_ORDER.map((a) => costs[a]), 0.01);
  const cheapest = ACTION_ORDER.reduce((best, a) => (costs[a] < costs[best] ? a : best));

  return (
    <div>
      <p className="flex flex-wrap items-center gap-2">
        Decision: <ActionBadge action={action} />
      </p>
      <p className="mt-2 text-sm text-muted">
        The policy picks the action with the lowest expected cost.
        {action !== cheapest &&
          " Reviewing was cheapest here, but that day's 30 review slots went to cases where a review saves more."}
      </p>
      <dl className="mt-3 space-y-2">
        {ACTION_ORDER.map((a) => (
          <div key={a}>
            <div className="flex justify-between text-sm">
              <dt className={a === action ? `font-semibold ${ACTION_STYLES[a].text}` : ""}>
                {ACTION_STYLES[a].label}
                {a === action && " (chosen)"}
              </dt>
              <dd className={a === action ? "font-semibold" : ""}>{money(costs[a])}</dd>
            </div>
            <div className="mt-1 h-3 rounded-sm bg-line" aria-hidden="true">
              <div
                className={`h-3 rounded-sm ${ACTION_STYLES[a].bar} ${a === action ? "" : "opacity-40"}`}
                style={{ width: `${Math.max((costs[a] / largest) * 100, 1)}%` }}
              />
            </div>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-muted">
        Approve = probability × amount (the fraud we&apos;d lose). Review = an analyst&apos;s time. Block = (1 −
        probability) × the cost of turning away a real customer.
      </p>
    </div>
  );
}

type Submit =
  | { status: "idle" }
  | { status: "sending" }
  | { status: "done"; result: ReviewResult }
  | { status: "error"; message: string };

function Decision({ id }: { id: string }) {
  const [note, setNote] = useState("");
  const [submit, setSubmit] = useState<Submit>({ status: "idle" });
  const busy = submit.status === "sending";

  async function decide(decision: "fraud" | "legitimate") {
    setSubmit({ status: "sending" });
    try {
      const result = await apiPost<ReviewResult>(`/review/${id}`, { decision, note: note.trim() || null });
      setSubmit({ status: "done", result });
    } catch (error) {
      setSubmit({ status: "error", message: error instanceof Error ? errorMessage(error) : "Something went wrong." });
    }
  }

  if (submit.status === "done") {
    const { result } = submit;
    return (
      <div
        role="status"
        className={`rounded-md p-4 ${result.correct ? "bg-approve-light text-approve" : "bg-block-light text-block"}`}
      >
        <p className="font-semibold">
          {result.correct ? "Correct." : "Not quite."} This transaction was actually{" "}
          {result.is_fraud ? "fraud" : "legitimate"}.
        </p>
        <p className="mt-1 text-sm text-muted">
          You marked it {result.decision}. Your decision has been saved.
        </p>
      </div>
    );
  }

  return (
    <div>
      <p className="text-sm text-muted">Is this fraud? Decide, and the app will show you the true answer.</p>
      <label className="mt-3 block text-sm font-medium">
        Note (optional)
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          maxLength={500}
          rows={2}
          disabled={busy}
          className="mt-1 block w-full rounded-md border border-line px-3 py-2 font-normal"
        />
      </label>
      <div className="mt-3 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => decide("fraud")}
          disabled={busy}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          Confirm fraud
        </button>
        <button
          type="button"
          onClick={() => decide("legitimate")}
          disabled={busy}
          className="rounded-md border border-accent px-4 py-2 text-sm font-medium text-accent disabled:opacity-50"
        >
          Mark legitimate
        </button>
      </div>
      <p className="mt-2 text-sm text-muted" aria-live="polite">
        {busy && "Saving…"}
        {submit.status === "error" && <span role="alert">Couldn&apos;t save: {submit.message}</span>}
      </p>
    </div>
  );
}
