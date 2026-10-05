"use client";

import { useEffect, useState } from "react";
import { ApiError, apiGet } from "./api";

// Free hosting sleeps when idle, so the first request can take 30 s or more.
const SLOW_AFTER_MS = 3000;

export type FetchState<T> =
  | { status: "loading" }
  | { status: "loaded"; data: T }
  | { status: "error"; error: ApiError | Error };

/**
 * GET `path` from the API. Returns the current state, whether the request has been
 * slow (so the page can explain a sleeping server), and a retry function.
 *
 * Each request is identified by path + attempt. Results are stored with that key, so
 * "loading" is simply "no result yet for the current key" and is never set by hand.
 */
export function useApiGet<T>(path: string) {
  const [attempt, setAttempt] = useState(0);
  const key = `${path}#${attempt}`;
  const [result, setResult] = useState<{ key: string; state: FetchState<T> } | null>(null);
  const [slowKey, setSlowKey] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const slowTimer = setTimeout(() => setSlowKey(key), SLOW_AFTER_MS);
    apiGet<T>(path, { signal: controller.signal })
      .then((data) => setResult({ key, state: { status: "loaded", data } }))
      .catch((error) => {
        if (controller.signal.aborted) return; // replaced by a newer request
        const failure = error instanceof Error ? error : new Error("Couldn't reach the API.");
        setResult({ key, state: { status: "error", error: failure } });
      })
      .finally(() => clearTimeout(slowTimer));
    return () => {
      controller.abort();
      clearTimeout(slowTimer);
    };
  }, [path, key]);

  const state: FetchState<T> = result?.key === key ? result.state : { status: "loading" };
  return { state, slow: slowKey === key, retry: () => setAttempt((n) => n + 1) };
}

export function errorMessage(error: Error): string {
  return error instanceof ApiError ? error.message : "Couldn't reach the API. Check your connection and try again.";
}
