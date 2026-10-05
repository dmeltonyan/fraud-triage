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

export type PolicyName = "approve_all" | "threshold" | "cost_review_only" | "cost_based";

export type PolicyOutcome = {
  fraud_dollars_lost: number;
  fraud_dollars_caught: number;
  frauds_caught: number;
  frauds_missed: number;
  reviews: number;
  blocks: number;
  legit_declined: number;
  total_cost: number;
};

/** The parts of reports/policy_results.json (GET /stats) the results page uses. */
export type Stats = {
  test_months: string[];
  transactions: number;
  frauds: number;
  fraud_dollars: number;
  costs: { review_cost_usd: number; false_decline_cost_usd: number };
  default_budget: number;
  default: Record<PolicyName, PolicyOutcome>;
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

export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return request<T>(path, init); // init can carry an AbortSignal to cancel a stale request
}

export function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
