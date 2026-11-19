// Thin client for the DxReview HTTP API. `fetch` is injectable for tests.

export type Decision = "APPROVE" | "NEEDS_INFO" | "CLINICAL_REVIEW";

export interface ReviewRequest {
  request_id: string;
  cpt_code: string;
  note: string;
  icd10_codes?: string[];
  payer?: string;
}

export interface CriterionResult {
  criterion_id: string;
  text: string;
  group: string;
  status: "MET" | "NOT_MET" | "NOT_FOUND" | "AMBIGUOUS";
  quote: string | null;
  quote_verified: boolean;
  notes: string[];
}

export interface ReviewResult {
  request_id: string;
  decision: Decision;
  reasons: string[];
  policy_id: string | null;
  policy_version: string | null;
  prompt_version: string;
  model: string;
  criteria: CriterionResult[];
  missing_criteria: string[];
  flags: string[];
  phi_redactions: Record<string, number>;
}

export interface PolicySummary {
  id: string;
  title: string;
  version: string;
  cpt_codes: string[];
  criteria: { id: string; group: string; text: string }[];
}

export interface PolicyDetail extends PolicySummary {
  effective: string;
  body: string;
}

export interface CopilotAnswer {
  question: string;
  answer: string;
  citations: { chunk_id: string; policy_id: string; policy_version: string; section: string }[];
  model: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export class DxReviewApi {
  constructor(
    private baseUrl: string,
    private apiKey?: string,
    private fetchImpl: typeof fetch = globalThis.fetch,
  ) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private async call<T>(method: string, path: string, body?: unknown, headers: Record<string, string> = {}): Promise<T> {
    const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers: {
        "content-type": "application/json",
        ...(this.apiKey ? { "x-api-key": this.apiKey } : {}),
        ...headers,
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      // Do not surface the response body: validation errors may echo the note.
      throw new ApiError(res.status, `DxReview API ${method} ${path} failed with status ${res.status}`);
    }
    return (await res.json()) as T;
  }

  review(req: ReviewRequest, idempotencyKey?: string): Promise<ReviewResult> {
    return this.call("POST", "/v1/reviews", req, idempotencyKey ? { "idempotency-key": idempotencyKey } : {});
  }

  listPolicies(): Promise<PolicySummary[]> {
    return this.call("GET", "/v1/policies");
  }

  getPolicy(id: string): Promise<PolicyDetail> {
    return this.call("GET", `/v1/policies/${encodeURIComponent(id)}`);
  }

  ask(question: string, policyId?: string): Promise<CopilotAnswer> {
    return this.call("POST", "/v1/copilot/ask", { question, policy_id: policyId ?? null });
  }
}
