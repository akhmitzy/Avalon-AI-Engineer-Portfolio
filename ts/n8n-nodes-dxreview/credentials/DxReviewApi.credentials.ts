import type { IAuthenticateGeneric, ICredentialTestRequest, ICredentialType, INodeProperties } from "n8n-workflow";

export class DxReviewApi implements ICredentialType {
  name = "dxReviewApi";

  displayName = "DxReview API";

  // TODO(owner): replace [YOUR-GITHUB] with your GitHub user or org before publishing.
  documentationUrl = "https://github.com/[YOUR-GITHUB]/dxreview#n8n-community-node";

  properties: INodeProperties[] = [
    {
      displayName: "Base URL",
      name: "baseUrl",
      type: "string",
      default: "http://dxreview-api:8080",
      placeholder: "https://dxreview.internal.example.com",
    },
    {
      displayName: "API Key",
      name: "apiKey",
      type: "string",
      typeOptions: { password: true },
      default: "",
    },
  ];

  authenticate: IAuthenticateGeneric = {
    type: "generic",
    properties: { headers: { "X-API-Key": "={{$credentials.apiKey}}" } },
  };

  test: ICredentialTestRequest = {
    request: { baseURL: "={{$credentials.baseUrl}}", url: "/v1/policies", method: "GET" },
  };
}
