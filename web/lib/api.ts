// Talking to the FastAPI backend (DATA_BACKEND=postgres mode).

// Written out in full so Next.js can fill it in at build time; see web/.env.example.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type Action = "approve" | "review" | "block";

export type ExpectedCosts = { approve: number; review: number; block: number };

export type QueueItem = {
  transaction_id: string;
  timestamp: string;
  merchant: string;
  category: string;
  amount: number;
  fraud_probability: number;
  expected_loss: number;
  loss_prevented: number;
};

export type QueueResponse = { date: string; review_budget: number; cases: QueueItem[] };

export type TransactionDetail = {
  transaction_id: string;
  timestamp: string;
  merchant: string;
  category: string;
  amount: number;
  city: string;
  state: string;
  fraud_probability: number;
  action: Action;
  expected_costs: ExpectedCosts;
  loss_prevented: number;
  reasons: string[];
};

export type ReviewResult = {
  transaction_id: string;
  decision: "fraud" | "legitimate";
  note: string | null;
  reviewed_at: string;
  is_fraud: boolean;
  correct: boolean;
};

/** An error response from the API, with its status code and the API's message. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = typeof body?.detail === "string" ? body.detail : `Request failed (${response.status})`;
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export function apiGet<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
