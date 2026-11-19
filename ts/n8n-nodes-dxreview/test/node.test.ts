import assert from "node:assert/strict";
import { test } from "node:test";

import type { IExecuteFunctions, IHttpRequestOptions } from "n8n-workflow";

import { DxReviewApi } from "../credentials/DxReviewApi.credentials.js";
import { DxReview } from "../nodes/DxReview/DxReview.node.js";

type Params = Record<string, unknown>;

function ctx(operation: string, items: Params[], responses: unknown[], calls: IHttpRequestOptions[], failMode = false) {
  let n = 0;
  return {
    getInputData: () => items.map((json) => ({ json })),
    getNodeParameter: (name: string, i: number, fallback?: unknown) => {
      if (name === "operation") return operation;
      const v = items[i]?.[name];
      return v === undefined ? fallback : v;
    },
    getCredentials: async () => ({ baseUrl: "http://api.test/", apiKey: "k" }),
    getNode: () => ({ name: "DxReview" }),
    continueOnFail: () => failMode,
    helpers: {
      httpRequestWithAuthentication: async function (_cred: string, opts: IHttpRequestOptions) {
        calls.push(opts);
        const r = responses[n++];
        if (r instanceof Error) throw r;
        return r;
      },
    },
  } as unknown as IExecuteFunctions;
}

test("review routes each decision to its own output with idempotency key", async () => {
  const calls: IHttpRequestOptions[] = [];
  const items = ["APPROVE", "NEEDS_INFO", "CLINICAL_REVIEW"].map((d, i) => ({ requestId: `r-${i}`, cptCode: "82306", note: "n", d }));
  const out = await new DxReview().execute.call(ctx("review", items, items.map((x) => ({ decision: x.d })), calls));
  assert.deepEqual(out.map((o) => o.length), [1, 1, 1]);
  assert.equal(calls[0].baseURL, "http://api.test");
  assert.deepEqual(calls[1].headers, { "Idempotency-Key": "r-1" });
});

test("unexpected decision values go to clinical review", async () => {
  const out = await new DxReview().execute.call(
    ctx("review", [{ requestId: "r", cptCode: "82306", note: "n" }], [{ decision: "DENY" }], []),
  );
  assert.deepEqual(out.map((o) => o.length), [0, 0, 1]);
});

test("continueOnFail keeps the error but not the note", async () => {
  const out = await new DxReview().execute.call(
    ctx("review", [{ requestId: "r", cptCode: "82306", note: "Jane Doe secret" }], [new Error("status 500")], [], true),
  );
  assert.equal(out[2][0].json.error, "status 500");
  assert.doesNotMatch(JSON.stringify(out), /Jane Doe/);
});

test("credentials send the API key header and test the policies route", () => {
  const c = new DxReviewApi();
  assert.deepEqual(c.authenticate.properties.headers, { "X-API-Key": "={{$credentials.apiKey}}" });
  assert.equal(c.test.request.url, "/v1/policies");
});
