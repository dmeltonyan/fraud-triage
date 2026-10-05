"use client"; // date picker, loading states and fetching run in the browser

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, apiGet, type QueueItem, type QueueResponse } from "@/lib/api";
import { categoryName, money, percent, timeOfDay } from "@/lib/format";

// The demo holds the test months only.
const FIRST_DAY = "2020-10-01";
const LAST_DAY = "2020-12-31";
const SLOW_AFTER_MS = 3000; // free hosting sleeps when idle; the first request can take 30 s or more

type Outcome = { status: "loaded"; data: QueueResponse } | { status: "empty" } | { status: "error"; message: string };
type State = { status: "loading" } | Outcome;

function validDay(value: string | null): string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) && value >= FIRST_DAY && value <= LAST_DAY ? value : FIRST_DAY;
}

export default function QueueView() {
  const router = useRouter();
  const pathname = usePathname();
  const day = validDay(useSearchParams().get("date"));
  const [attempt, setAttempt] = useState(0); // bumped by Retry

  // Each request is identified by day + attempt. Results are stored with that key,
  // so "loading" is simply "no result yet for the current key" and is never set by hand.
  const requestKey = `${day}#${attempt}`;
  const [result, setResult] = useState<{ key: string; outcome: Outcome } | null>(null);
  const [slowKey, setSlowKey] = useState<string | null>(null);
  const state: State = result?.key === requestKey ? result.outcome : { status: "loading" };
  const slow = slowKey === requestKey;

  useEffect(() => {
    const controller = new AbortController();
    const finish = (outcome: Outcome) => setResult({ key: requestKey, outcome });
    const slowTimer = setTimeout(() => setSlowKey(requestKey), SLOW_AFTER_MS);

    apiGet<QueueResponse>(`/queue?date=${day}`, { signal: controller.signal })
      .then((data) => finish(data.cases.length ? { status: "loaded", data } : { status: "empty" }))
      .catch((error) => {
        if (controller.signal.aborted) return; // a newer date was picked
        if (error instanceof ApiError && error.status === 404) finish({ status: "empty" });
        else finish({ status: "error", message: error instanceof ApiError ? error.message : "Couldn't reach the API." });
      })
      .finally(() => clearTimeout(slowTimer));

    return () => {
      controller.abort();
      clearTimeout(slowTimer);
    };
  }, [day, requestKey]);

  function pickDay(value: string) {
    // Keep the day in the URL so Back from a case returns to it.
    router.replace(`${pathname}?date=${validDay(value)}`);
  }

  return (
    <section>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Review queue</h1>
          <p className="mt-1 text-muted">Cases the cost-based policy sent to an analyst, largest expected loss first.</p>
        </div>
        <label className="flex flex-col text-sm font-medium">
          Day
          <input
            type="date"
            value={day}
            min={FIRST_DAY}
            max={LAST_DAY}
            onChange={(event) => event.target.value && pickDay(event.target.value)}
            className="mt-1 rounded-md border border-line px-3 py-2 font-normal"
          />
        </label>
      </div>

      <div className="mt-6" aria-live="polite">
        {state.status === "loading" && (
          <p className="text-muted">
            Loading cases for {day}…
            {slow && (
              <span className="mt-2 block">
                The demo server is probably waking up after being idle. This can take up to a minute the first time.
              </span>
            )}
          </p>
        )}

        {state.status === "empty" && <p className="text-muted">No review cases on {day}. Try another day.</p>}

        {state.status === "error" && (
          <div role="alert" className="rounded-md border border-line p-4">
            <p>Couldn&apos;t load the queue: {state.message}</p>
            <button
              type="button"
              onClick={() => setAttempt((n) => n + 1)}
              className="mt-3 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white"
            >
              Retry
            </button>
          </div>
        )}

        {state.status === "loaded" && <CaseList data={state.data} />}
      </div>
    </section>
  );
}

function CaseList({ data }: { data: QueueResponse }) {
  return (
    <>
      <p className="mb-3 text-sm text-muted">
        {data.cases.length} case{data.cases.length === 1 ? "" : "s"} (daily budget {data.review_budget})
      </p>

      {/* Wider screens: a table */}
      <table className="hidden w-full text-left text-sm sm:table">
        <thead className="border-b border-line text-muted">
          <tr>
            <th className="py-2 font-medium">Time</th>
            <th className="py-2 font-medium">Merchant</th>
            <th className="py-2 font-medium">Category</th>
            <th className="py-2 text-right font-medium">Amount</th>
            <th className="py-2 text-right font-medium">Fraud probability</th>
            <th className="py-2 text-right font-medium">Expected loss</th>
          </tr>
        </thead>
        <tbody>
          {data.cases.map((c) => (
            <tr key={c.transaction_id} className="border-b border-line hover:bg-accent-light">
              <td className="py-2">{timeOfDay(c.timestamp)}</td>
              <td className="py-2">
                <Link href={`/case/${c.transaction_id}`} className="font-medium text-accent hover:underline">
                  {c.merchant}
                </Link>
              </td>
              <td className="py-2">{categoryName(c.category)}</td>
              <td className="py-2 text-right">{money(c.amount)}</td>
              <td className="py-2 text-right">{percent(c.fraud_probability)}</td>
              <td className="py-2 text-right">{money(c.expected_loss)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Narrow screens (under 640 px): stacked cards */}
      <ul className="space-y-3 sm:hidden">
        {data.cases.map((c) => (
          <CaseCard key={c.transaction_id} item={c} />
        ))}
      </ul>
    </>
  );
}

function CaseCard({ item }: { item: QueueItem }) {
  return (
    <li>
      <Link href={`/case/${item.transaction_id}`} className="block rounded-md border border-line p-4 hover:bg-accent-light">
        <div className="flex justify-between gap-2">
          <span className="font-medium text-accent">{item.merchant}</span>
          <span className="font-medium">{money(item.amount)}</span>
        </div>
        <div className="mt-1 text-sm text-muted">
          {timeOfDay(item.timestamp)} · {categoryName(item.category)}
        </div>
        <div className="mt-2 flex justify-between text-sm">
          <span>Fraud probability {percent(item.fraud_probability)}</span>
          <span>Expected loss {money(item.expected_loss)}</span>
        </div>
      </Link>
    </li>
  );
}
