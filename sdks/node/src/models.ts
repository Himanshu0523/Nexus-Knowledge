export interface DocumentSource {
  document: string;
  page?: number;
  relevanceScore?: number;
}

export interface UsageInfo {
  inputTokens: number;
  outputTokens: number;
}

export interface ChatResponse {
  conversationId: string;
  messageId: string;
  text: string;
  sources?: DocumentSource[];
  usage?: UsageInfo;
  model?: string;
}

export interface StreamEvent {
  type: "status" | "token" | "source" | "tool_start" | "tool_result" | "error" | "done" | "metadata";
  eventId?: string;
  timestamp?: number;
  content?: string;
  status?: string;
  message?: string;
  source?: string;
  page?: number;
  toolName?: string;
  arguments?: Record<string, any>;
  result?: Record<string, any>;
  messageId?: string;
  usage?: Record<string, number>;
}

export interface ClientConfig {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  tenantId?: string;
}
