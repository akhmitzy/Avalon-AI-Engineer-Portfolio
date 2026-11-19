#!/usr/bin/env node
// stdio entrypoint. Configure with DXREVIEW_API_URL and DXREVIEW_API_KEY.
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { DxReviewApi } from "./api.js";
import { createServer } from "./server.js";

const api = new DxReviewApi(process.env.DXREVIEW_API_URL ?? "http://localhost:8080", process.env.DXREVIEW_API_KEY);
const server = createServer(api);
await server.connect(new StdioServerTransport());
// stdout carries the protocol; log to stderr only.
console.error("dxreview MCP server running on stdio");
