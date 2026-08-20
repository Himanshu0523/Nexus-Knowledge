import fetch from "node-fetch";
import { ClientConfig, ChatResponse, StreamEvent } from "./models";
import { ChatbotError, AuthenticationError, InvalidRequestError } from "./errors";

export class ChatbotClient {
  private apiKey?: string;
  private baseUrl: string;
  private timeout: number;
  private tenantId: string;

  constructor(config: ClientConfig = {}) {
    this.apiKey = config.apiKey;
    this.baseUrl = (config.baseUrl || "http://localhost:8000").replace(/\/$/, "");
    this.timeout = config.timeout || 60000;
    this.tenantId = config.tenantId || "default";
  }

  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "User-Agent": "Chatbot-Node-SDK/1.0.0",
    };
    if (this.apiKey) {
      headers["X-API-Key"] = this.apiKey;
      headers["Authorization"] = `Bearer ${this.apiKey}`;
    }
    return headers;
  }

  public async chat(
    message: string,
    conversationId?: string,
    knowledgeBaseId?: string,
    metadata?: Record<string, any>
  ): Promise<ChatResponse> {
    const convId = conversationId || `conv_${Math.random().toString(36).substring(2, 12)}`;
    const meta = metadata || {};
    meta["tenant_id"] = this.tenantId;

    const payload = {
      conversation_id: convId,
      message,
      knowledge_base_id: knowledgeBaseId,
      metadata: meta,
    };

    const response = await fetch(`${this.baseUrl}/api/v1/chat`, {
      method: "POST",
      headers: this.getHeaders(),
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const code = errData?.error?.code || "API_ERROR";
      const msg = errData?.error?.message || response.statusText;
      if (response.status === 401 || response.status === 403) {
        throw new AuthenticationError(msg);
      } else if (response.status === 400) {
        throw new InvalidRequestError(msg);
      }
      throw new ChatbotError(msg, code, undefined, response.status);
    }

    const data = await response.json();
    return {
      conversationId: data.conversation_id,
      messageId: data.message_id,
      text: data.response,
      sources: data.sources,
      usage: data.usage,
      model: data.model,
    };
  }
}
