package com.chatbot.models;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

public class ChatResponse {
    @JsonProperty("conversation_id")
    private String conversationId;

    @JsonProperty("message_id")
    private String messageId;

    @JsonProperty("response")
    private String text;

    private List<Map<String, Object>> sources;
    private Map<String, Integer> usage;
    private String model;

    public String getConversationId() { return conversationId; }
    public String getMessageId() { return messageId; }
    public String getText() { return text; }
    public List<Map<String, Object>> getSources() { return sources; }
    public Map<String, Integer> getUsage() { return usage; }
    public String getModel() { return model; }
}
