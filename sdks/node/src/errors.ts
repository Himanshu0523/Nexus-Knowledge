export class ChatbotError extends Error {
  public code: string;
  public requestId?: string;
  public statusCode?: number;

  constructor(message: string, code: string = "SDK_ERROR", requestId?: string, statusCode: number = 500) {
    super(message);
    this.name = "ChatbotError";
    this.code = code;
    this.requestId = requestId;
    this.statusCode = statusCode;
  }
}

export class AuthenticationError extends ChatbotError {
  constructor(message: string = "Unauthorized API key", requestId?: string) {
    super(message, "UNAUTHORIZED", requestId, 401);
    this.name = "AuthenticationError";
  }
}

export class InvalidRequestError extends ChatbotError {
  constructor(message: string, requestId?: string) {
    super(message, "INVALID_REQUEST", requestId, 400);
    this.name = "InvalidRequestError";
  }
}
