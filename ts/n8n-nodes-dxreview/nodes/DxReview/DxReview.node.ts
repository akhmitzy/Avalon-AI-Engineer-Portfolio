import {
  type IDataObject,
  type IExecuteFunctions,
  type IHttpRequestOptions,
  type INodeExecutionData,
  type INodeType,
  type INodeTypeDescription,
  NodeConnectionTypes,
  NodeOperationError,
} from "n8n-workflow";

/**
 * DxReview node. Three outputs for the Review operation (APPROVE, NEEDS_INFO,
 * CLINICAL_REVIEW) so workflows route on the deterministic decision without
 * an IF node. There is no DENY output because the API cannot produce one.
 */
export class DxReview implements INodeType {
  description: INodeTypeDescription = {
    displayName: "DxReview",
    name: "dxReview",
    icon: "file:dxreview.svg",
    group: ["transform"],
    version: 1,
    subtitle: '={{$parameter["operation"]}}',
    description: "Prior-authorization evidence review for lab and genetic tests",
    defaults: { name: "DxReview" },
    inputs: [NodeConnectionTypes.Main],
    outputs: `={{ $parameter["operation"] === "review"
      ? [{type: "main", displayName: "Approve"}, {type: "main", displayName: "Needs info"}, {type: "main", displayName: "Clinical review"}]
      : [{type: "main"}] }}`,
    credentials: [{ name: "dxReviewApi", required: true }],
    usableAsTool: true,
    properties: [
      {
        displayName: "Operation",
        name: "operation",
        type: "options",
        noDataExpression: true,
        options: [
          { name: "Review Request", value: "review", action: "Review a prior authorization request" },
          { name: "Ask Policy Copilot", value: "ask", action: "Ask the policy copilot" },
          { name: "Get Policy", value: "getPolicy", action: "Get a coverage policy" },
        ],
        default: "review",
      },
      {
        displayName: "Request ID",
        name: "requestId",
        type: "string",
        required: true,
        default: "={{ $json.request_id }}",
        displayOptions: { show: { operation: ["review"] } },
        description: "Also used as the Idempotency-Key, so n8n retries never double-process",
      },
      {
        displayName: "CPT Code",
        name: "cptCode",
        type: "string",
        required: true,
        default: "={{ $json.cpt_code }}",
        displayOptions: { show: { operation: ["review"] } },
      },
      {
        displayName: "Clinical Note",
        name: "note",
        type: "string",
        typeOptions: { rows: 6 },
        required: true,
        default: "={{ $json.note }}",
        displayOptions: { show: { operation: ["review"] } },
        description: "PHI is scrubbed by the API before any model sees it",
      },
      {
        displayName: "Question",
        name: "question",
        type: "string",
        required: true,
        default: "",
        displayOptions: { show: { operation: ["ask"] } },
      },
      {
        displayName: "Policy ID",
        name: "policyId",
        type: "string",
        default: "",
        placeholder: "LAB-GEN-001",
        displayOptions: { show: { operation: ["ask", "getPolicy"] } },
        description: "Required for Get Policy; optional filter for Ask",
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const operation = this.getNodeParameter("operation", 0) as string;
    const creds = await this.getCredentials("dxReviewApi");
    const baseURL = String(creds.baseUrl).replace(/\/+$/, "");
    const approve: INodeExecutionData[] = [];
    const needsInfo: INodeExecutionData[] = [];
    const review: INodeExecutionData[] = [];
    const single: INodeExecutionData[] = [];

    for (let i = 0; i < items.length; i++) {
      try {
        if (operation === "review") {
          const requestId = this.getNodeParameter("requestId", i) as string;
          const options: IHttpRequestOptions = {
            method: "POST",
            baseURL,
            url: "/v1/reviews",
            headers: { "Idempotency-Key": requestId },
            body: {
              request_id: requestId,
              cpt_code: this.getNodeParameter("cptCode", i) as string,
              note: this.getNodeParameter("note", i) as string,
            },
            json: true,
          };
          const result = (await this.helpers.httpRequestWithAuthentication.call(this, "dxReviewApi", options)) as IDataObject;
          const out = { json: result, pairedItem: { item: i } };
          if (result.decision === "APPROVE") approve.push(out);
          else if (result.decision === "NEEDS_INFO") needsInfo.push(out);
          else review.push(out); // CLINICAL_REVIEW, and anything unexpected, goes to a human
        } else if (operation === "ask") {
          const policyId = this.getNodeParameter("policyId", i, "") as string;
          const result = await this.helpers.httpRequestWithAuthentication.call(this, "dxReviewApi", {
            method: "POST",
            baseURL,
            url: "/v1/copilot/ask",
            body: { question: this.getNodeParameter("question", i) as string, policy_id: policyId || null },
            json: true,
          });
          single.push({ json: result as IDataObject, pairedItem: { item: i } });
        } else if (operation === "getPolicy") {
          const policyId = this.getNodeParameter("policyId", i, "") as string;
          if (!policyId) throw new NodeOperationError(this.getNode(), "Policy ID is required", { itemIndex: i });
          const result = await this.helpers.httpRequestWithAuthentication.call(this, "dxReviewApi", {
            method: "GET",
            baseURL,
            url: `/v1/policies/${encodeURIComponent(policyId)}`,
            json: true,
          });
          single.push({ json: result as IDataObject, pairedItem: { item: i } });
        } else {
          throw new NodeOperationError(this.getNode(), `Unknown operation ${operation}`, { itemIndex: i });
        }
      } catch (error) {
        if (this.continueOnFail()) {
          // Never echo the note into error output.
          const failed = { json: { error: (error as Error).message, request_index: i }, pairedItem: { item: i } };
          if (operation === "review") review.push(failed);
          else single.push(failed);
          continue;
        }
        throw error;
      }
    }
    return operation === "review" ? [approve, needsInfo, review] : [single];
  }
}
