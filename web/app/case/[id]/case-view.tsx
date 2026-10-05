"use client"; // loads the case and handles the decision buttons in the browser

import Link from "next/link";
import { useState } from "react";
import { ApiError, apiPost, type Action, type ReviewResult, type TransactionDetail } from "@/lib/api";
import { categoryName, dateTime, money, percent } from "@/lib/format";
import { errorMessage, useApiGet } from "@/lib/use-api";
import { LoadError, Loading } from "../../status";

const ACTION_LABELS: Record<Action, string> = { approve: "Approve", review: "Review", block: "Block" };

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
          <Link href="/" className="mt-4 inline-block text-accent hover:underline">
            ← Back to the queue
          </Link>
        </section>
      );
    }
    return <LoadError message={`Couldn't load the case. ${errorMessage(state.error)}`} onRetry={retry} />;
  }

  const c = state.data;
  return (
    <section>
      <Link href={`/?date=${c.timestamp.slice(0, 10)}`} className="text-sm text-accent hover:underline">
        ← Back to the queue for {c.timestamp.slice(0, 10)}
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{c.merchant}</h1>
          <p className="mt-1 text-muted">
            {categoryName(c.category)} · {c.city}, {c.state} · {dateTime(c.timestamp)}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold">{money(c.amount)}</div>
          <div className="text-sm text-muted">Fraud probability {percent(c.fraud_probability)}</div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div>
          <h2 className="font-semibold">Why the model scored it this way</h2>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            {c.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ol>
        </div>
        <CostBars costs={c.expected_costs} action={c.action} />
      </div>

      <Decision id={c.transaction_id} />
    </section>
  );
}

function CostBars({ costs, action }: { costs: TransactionDetail["expected_costs"]; action: Action }) {
  const actions: Action[] = ["approve", "review", "block"];
  const largest = Math.max(...actions.map((a) => costs[a]), 0.01);
  const cheapest = actions.reduce((best, a) => (costs[a] < costs[best] ? a : best));

  return (
    <div>
      <h2 className="font-semibold">Expected cost of each action</h2>
      <p className="mt-1 text-sm text-muted">
        The policy chose <strong className="text-foreground">{ACTION_LABELS[action].toLowerCase()}</strong>.
        {action !== cheapest &&
          ` Reviewing was cheapest, but that day's review budget was already used by cases where a review saves more.`}
      </p>
      <dl className="mt-3 space-y-2">
        {actions.map((a) => (
          <div key={a}>
            <div className="flex justify-between text-sm">
              <dt className={a === action ? "font-semibold" : ""}>
                {ACTION_LABELS[a]}
                {a === action && " (chosen)"}
              </dt>
              <dd>{money(costs[a])}</dd>
            </div>
            <div className="mt-1 h-3 rounded-sm bg-line" aria-hidden="true">
              <div
                className={`h-3 rounded-sm ${a === action ? "bg-accent" : "bg-muted"}`}
                style={{ width: `${Math.max((costs[a] / largest) * 100, 1)}%` }}
              />
            </div>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-muted">
        Approve = probability × amount. Review = analyst cost. Block = (1 − probability) × cost of declining a real
        customer.
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
      <div role="status" className="mt-8 rounded-md border border-line p-4">
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
    <div className="mt-8 rounded-md border border-line p-4">
      <h2 className="font-semibold">Your decision</h2>
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
