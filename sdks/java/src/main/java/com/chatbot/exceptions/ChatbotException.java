package com.chatbot.exceptions;

public class ChatbotException extends Exception {
    private final String code;
    private final int statusCode;

    public ChatbotException(String message, String code, int statusCode) {
        super(message);
        this.code = code;
        this.statusCode = statusCode;
    }

    public String getCode() {
        return code;
    }

    public int getStatusCode() {
        return statusCode;
    }
}
