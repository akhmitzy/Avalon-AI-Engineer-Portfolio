// DxReview MCP server: tools, policy resources and prompts.
//
// Tools never return DENY (the API cannot produce one) and always tell the
// calling agent that the decision came from deterministic rules, so an agent
// does not "re-decide" a CLINICAL_REVIEW case on its own.

import { McpServer, ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

import { ApiError, DxReviewApi, type ReviewResult } from "./api.js";

export const SERVER_NAME = "dxreview";
export const SERVER_VERSION = "0.3.0";

function text(t: string) {
  return { content: [{ type: "text" as const, text: t }] };
}

function errorResult(e: unknown) {
  const msg = e instanceof ApiError ? e.message : `DxReview request failed: ${(e as Error).message}`;
  return { ...text(msg), isError: true };
}

export function formatReview(r: ReviewResult): string {
  const lines = [
    `Decision: ${r.decision} (made by deterministic rules, not by a model)`,
    `Policy: ${r.policy_id ?? "none"} v${r.policy_version ?? "-"} | prompt ${r.prompt_version} | model ${r.model}`,
    `Reasons: ${r.reasons.join("; ")}`,
  ];
  if (r.flags.length) lines.push(`Safety flags: ${r.flags.join(", ")}`);
  if (r.missing_criteria.length) lines.push(`Missing documentation: ${r.missing_criteria.join(", ")}`);
  for (const c of r.criteria) {
    const q = c.quote ? ` "${c.quote}"${c.quote_verified ? "" : " (quote NOT verified)"}` : "";
    lines.push(`- [${c.status}] ${c.criterion_id}:${q}`);
  }
  if (r.decision === "CLINICAL_REVIEW") {
    lines.push("A licensed clinician must review this request. Do not approve or deny it yourself.");
  }
  return lines.join("\n");
}

export function createServer(api: DxReviewApi): McpServer {
  const server = new McpServer({ name: SERVER_NAME, version: SERVER_VERSION });

  server.registerTool(
    "review_prior_auth",
    {
      title: "Review a prior-authorization request",
      description:
        "Run DxReview on a lab or genetic test request. Returns APPROVE, NEEDS_INFO or CLINICAL_REVIEW with per-criterion evidence quotes. PHI is scrubbed server-side before any model sees the note.",
      inputSchema: {
        request_id: z.string().min(1).max(128),
        cpt_code: z.string().regex(/^\d{4}[0-9A-Z]$/, "5-character CPT code"),
        note: z.string().min(1).max(200_000),
        icd10_codes: z.array(z.string()).optional(),
        idempotency_key: z.string().optional(),
      },
      annotations: { readOnlyHint: false, idempotentHint: true, openWorldHint: false },
    },
    async ({ idempotency_key, ...req }) => {
      try {
        const r = await api.review(req, idempotency_key ?? req.request_id);
        return { ...text(formatReview(r)), structuredContent: r as unknown as Record<string, unknown> };
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  server.registerTool(
    "ask_policy_copilot",
    {
      title: "Ask the policy copilot",
      description: "Answer a question about coverage policies. Answers cite policy sections by id.",
      inputSchema: { question: z.string().min(3).max(2000), policy_id: z.string().optional() },
      annotations: { readOnlyHint: true },
    },
    async ({ question, policy_id }) => {
      try {
        const a = await api.ask(question, policy_id);
        const cites = a.citations.map((c) => `- ${c.chunk_id} (${c.policy_id} v${c.policy_version}, ${c.section})`);
        return text([a.answer, "", "Citations:", ...(cites.length ? cites : ["(none)"])].join("\n"));
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  server.registerTool(
    "list_policies",
    {
      title: "List coverage policies",
      description: "List policies with their CPT codes and criteria ids.",
      inputSchema: {},
      annotations: { readOnlyHint: true },
    },
    async () => {
      try {
        const ps = await api.listPolicies();
        return text(ps.map((p) => `${p.id} v${p.version}: ${p.title} [CPT ${p.cpt_codes.join(", ")}]`).join("\n"));
      } catch (e) {
        return errorResult(e);
      }
    },
  );

  server.registerResource(
    "policy",
    new ResourceTemplate("policy://{policyId}", {
      list: async () => ({
        resources: (await api.listPolicies()).map((p) => ({
          uri: `policy://${p.id}`,
          name: p.id,
          title: p.title,
          mimeType: "text/markdown",
        })),
      }),
    }),
    { title: "Coverage policy", description: "Full text of a coverage policy", mimeType: "text/markdown" },
    async (uri, { policyId }) => {
      const p = await api.getPolicy(String(policyId));
      return {
        contents: [{ uri: uri.href, mimeType: "text/markdown", text: `# ${p.title} (v${p.version})\n\n${p.body}` }],
      };
    },
  );

  server.registerPrompt(
    "summarize_review_for_provider",
    {
      title: "Summarize a review for the ordering provider",
      description: "Turn a DxReview result into a short, neutral message for the ordering provider.",
      argsSchema: { review_json: z.string() },
    },
    ({ review_json }) => ({
      messages: [
        {
          role: "user",
          content: {
            type: "text",
            text:
              "Write a short, neutral message to the ordering provider about this prior-authorization review. " +
              "State the outcome exactly as given. If it is NEEDS_INFO, list the missing documentation as a checklist. " +
              "If it is CLINICAL_REVIEW, say a clinician will review it; do not speculate about the outcome. " +
              "Never describe the outcome as a denial. Do not include any patient identifiers.\n\n" +
              `<review>${review_json}</review>`,
          },
        },
      ],
    }),
  );

  server.registerPrompt(
    "draft_missing_info_request",
    {
      title: "Draft a request for missing documentation",
      description: "Draft a request to the provider's office for the documentation a policy needs.",
      argsSchema: { policy_id: z.string(), missing_criteria: z.string().describe("comma-separated criterion ids") },
    },
    async ({ policy_id, missing_criteria }) => {
      const p = await api.getPolicy(policy_id);
      const wanted = new Set(missing_criteria.split(",").map((s) => s.trim()));
      const items = p.criteria.filter((c) => wanted.has(c.id)).map((c) => `- ${c.text}`);
      return {
        messages: [
          {
            role: "user",
            content: {
              type: "text",
              text:
                `Draft a brief, polite request to the ordering provider's office for documentation needed under ` +
                `${p.title} (v${p.version}). Ask for clinical notes that show:\n${items.join("\n")}\n` +
                `Do not mention any patient identifiers.`,
            },
          },
        ],
      };
    },
  );

  return server;
}
