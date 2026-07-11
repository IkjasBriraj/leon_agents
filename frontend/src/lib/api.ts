/**
 * API Client — AgentCraft
 *
 * Wraps all REST requests to the FastAPI backend.
 * Automatically injects the JWT access token from cookies if present.
 * Standardizes error handling and response parsing.
 */

import Cookies from "js-cookie";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1";

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export class ApiError extends Error {
  status: number;
  detail: any;

  constructor(status: number, message: string, detail?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Perform an HTTP request with automatic auth headers.
 */
async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { params, headers: customHeaders, ...rest } = options;

  // Build URL with query params
  let url = `${API_BASE_URL}${endpoint}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    });
    url += `?${searchParams.toString()}`;
  }

  // Build headers
  const headers = new Headers(customHeaders);
  if (!headers.has("Content-Type") && !(rest.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  // Inject JWT Token
  const token = Cookies.get("agentcraft_token");
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    headers,
    ...rest,
  });

  if (response.status === 204) {
    return {} as T;
  }

  let data;
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    // If 401, clean up token
    if (response.status === 401) {
      Cookies.remove("agentcraft_token");
    }
    const errMsg = data?.detail || response.statusText || "Request failed";
    throw new ApiError(response.status, errMsg, data);
  }

  return data as T;
}

// ─── API Methods ──────────────────────────────────────────────────────────────

export const api = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: "GET", ...options }),

  post: <T>(endpoint: string, body?: any, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    }),

  put: <T>(endpoint: string, body?: any, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    }),

  patch: <T>(endpoint: string, body?: any, options?: RequestOptions) =>
    request<T>(endpoint, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
      ...options,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { method: "DELETE", ...options }),
};

// ─── Typed API Endpoints ──────────────────────────────────────────────────────

export interface Organization {
  id: string;
  name: string;
  slug: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  org_id: string;
  is_active: boolean;
  created_at: string;
}

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  model_provider: string;
  model_name: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  system_prompt: string;
  persona: string | null;
  instructions: any[];
  max_iterations: number;
  timeout_seconds: number;
  status: string;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowNode {
  id: string;
  node_key: string;
  node_type: string;
  label: string | null;
  config: any;
  position_x: number;
  position_y: number;
  width: number | null;
  height: number | null;
}

export interface WorkflowEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  condition: any | null;
  label: string | null;
  priority: number;
  style: any;
}

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  is_cyclic: boolean;
  trigger_type: string;
  trigger_config: any;
  viewport: { x: number; y: number; zoom: number };
  status: string;
  version: number;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  created_at: string;
  updated_at: string;
}

export interface RunStep {
  id: string;
  step_index: number;
  node_key: string | null;
  step_type: string;
  model_used: string | null;
  tokens_in: number;
  tokens_out: number;
  cost_usd: string;
  tool_name: string | null;
  tool_input: any | null;
  tool_output: any | null;
  state_before: any | null;
  state_after: any | null;
  state_delta: any | null;
  memories_retrieved: any | null;
  started_at: string;
  completed_at: string | null;
  duration_ms: number | null;
  error: any | null;
}

export interface Run {
  id: string;
  org_id: string;
  workflow_id: string | null;
  status: string;
  input_data: any;
  output_data: any | null;
  error: any | null;
  total_steps: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost_usd: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  created_at: string;
  steps?: RunStep[];
}

export interface Memory {
  id: string;
  org_id: string;
  agent_id: string | null;
  memory_type: string;
  content: string;
  summary: string | null;
  tags: string[];
  metadata: any;
  importance: number;
  access_count: number;
  last_accessed: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MemorySearchResult {
  memory: Memory;
  score: number;
}
