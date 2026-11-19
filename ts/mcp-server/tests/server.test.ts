import assert from "node:assert/strict";
import { test } from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import { DxReviewApi } from "../src/api.js";
import { createServer } from "../src/server.js";

const POLICY = {
  id: "LAB-PGX-003",
  title: "CYP2C19 Genotyping for Clopidogrel Therapy",
  version: "2026.1",
  effective: "2026-01-01",
  cpt_codes: ["81225"],
  body: "## Coverage criteria\nCovered when clopidogrel is planned.",
  criteria: [
    { id: "clopidogrel_planned", group: "required", text: "Clopidogrel is planned." },
    { id: "cardiovascular_indication", group: "indication", text: "ACS or PCI." },
  ],
};

const REVIEW = {
  request_id: "r-1",
  decision: "CLINICAL_REVIEW",
  reasons: ["clopidogrel_planned:not_met"],
  policy_id: "LAB-PGX-003",
  policy_version: "2026.1",
  prompt_version: "extract-evidence/v3",
  model: "offline-rules/v2",
  criteria: [
    { criterion_id: "clopidogrel_planned", text: "", group: "required", status: "NOT_MET", quote: "Not a candidate for clopidogrel.", quote_verified: true, notes: [] },
  ],
  missing_criteria: [],
  flags: [],
  phi_redactions: {},
};

type Call = { url: string; init: RequestInit };

function fakeFetch(calls: Call[], status = 200): typeof fetch {
  return (async (url: string | URL, init: RequestInit = {}) => {
    calls.push({ url: String(url), init });
    const u = String(url);
    let body: unknown = {};
    if (u.endsWith("/v1/reviews")) body = REVIEW;
    else if (u.endsWith("/v1/policies")) body = [POLICY];
    else if (u.includes("/v1/policies/")) body = POLICY;
    else if (u.endsWith("/v1/copilot/ask"))
      body = { question: "q", answer: "Covered when planned [LAB-PGX-003#coverage-criteria]", model: "m",
               citations: [{ chunk_id: "LAB-PGX-003#coverage-criteria", policy_id: "LAB-PGX-003", policy_version: "2026.1", section: "Coverage criteria" }] };
    return new Response(JSON.stringify(status === 200 ? body : { detail: "note: Jane Doe" }), { status });
  }) as typeof fetch;
}

async function connect(calls: Call[], status = 200) {
  const server = createServer(new DxReviewApi("http://api.test/", "k-123", fakeFetch(calls, status)));
  const client = new Client({ name: "test", version: "0" });
  const [a, b] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(a), client.connect(b)]);
  return client;
}

test("lists tools, resources and prompts", async () => {
  const client = await connect([]);
  const tools = (await client.listTools()).tools.map((t) => t.name).sort();
  assert.deepEqual(tools, ["ask_policy_copilot", "list_policies", "review_prior_auth"]);
  const res = await client.listResources();
  assert.equal(res.resources[0].uri, "policy://LAB-PGX-003");
  const prompts = (await client.listPrompts()).prompts.map((p) => p.name).sort();
  assert.deepEqual(prompts, ["draft_missing_info_request", "summarize_review_for_provider"]);
});

test("review tool sends auth and idempotency headers and warns on clinical review", async () => {
  const calls: Call[] = [];
  const client = await connect(calls);
  const out = await client.callTool({ name: "review_prior_auth", arguments: { request_id: "r-1", cpt_code: "81225", note: "x" } });
  const h = calls[0].init.headers as Record<string, string>;
  assert.equal(calls[0].url, "http://api.test/v1/reviews");
  assert.equal(h["x-api-key"], "k-123");
  assert.equal(h["idempotency-key"], "r-1");
  const t = (out.content as { text: string }[])[0].text;
  assert.match(t, /Decision: CLINICAL_REVIEW \(made by deterministic rules/);
  assert.match(t, /Do not approve or deny it yourself/);
  assert.equal((out.structuredContent as { decision: string }).decision, "CLINICAL_REVIEW");
});

test("review tool validates CPT code before calling the API", async () => {
  const calls: Call[] = [];
  const client = await connect(calls);
  const out = await client.callTool({ name: "review_prior_auth", arguments: { request_id: "r", cpt_code: "abc", note: "x" } });
  assert.equal(out.isError, true);
  assert.equal(calls.length, 0);
});

test("API errors do not leak the response body", async () => {
  const client = await connect([], 422);
  const out = await client.callTool({ name: "review_prior_auth", arguments: { request_id: "r", cpt_code: "81225", note: "x" } });
  assert.equal(out.isError, true);
  const t = (out.content as { text: string }[])[0].text;
  assert.match(t, /status 422/);
  assert.doesNotMatch(t, /Jane Doe/);
});

test("copilot tool lists citations", async () => {
  const client = await connect([]);
  const out = await client.callTool({ name: "ask_policy_copilot", arguments: { question: "When is CYP2C19 covered?" } });
  assert.match((out.content as { text: string }[])[0].text, /LAB-PGX-003#coverage-criteria/);
});

test("policy resource and missing-info prompt", async () => {
  const client = await connect([]);
  const r = await client.readResource({ uri: "policy://LAB-PGX-003" });
  assert.match((r.contents[0] as { text: string }).text, /# CYP2C19 Genotyping/);
  const p = await client.getPrompt({ name: "draft_missing_info_request", arguments: { policy_id: "LAB-PGX-003", missing_criteria: "cardiovascular_indication" } });
  const t = (p.messages[0].content as { text: string }).text;
  assert.match(t, /ACS or PCI/);
  assert.doesNotMatch(t, /Clopidogrel is planned/);
});
