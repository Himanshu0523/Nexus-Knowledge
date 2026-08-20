class ChatbotError(Exception):
    """Base exception for Chatbot SDK"""
    def __init__(self, message: str, code: str = "SDK_ERROR", request_id: str = None, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.request_id = request_id
        self.status_code = status_code

class AuthenticationError(ChatbotError):
    """Authentication or authorization failure"""
    def __init__(self, message: str = "Invalid API key or unauthorized", request_id: str = None):
        super().__init__(message, code="UNAUTHORIZED", request_id=request_id, status_code=401)

class InvalidRequestError(ChatbotError):
    """Bad request parameters"""
    def __init__(self, message: str, request_id: str = None):
        super().__init__(message, code="INVALID_REQUEST", request_id=request_id, status_code=400)

class ConnectionError(ChatbotError):
    """Network connection failure"""
    def __init__(self, message: str = "Failed to connect to Chatbot API"):
        super().__init__(message, code="CONNECTION_ERROR", status_code=503)
