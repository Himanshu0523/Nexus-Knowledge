package com.chatbot;

import com.chatbot.exceptions.ChatbotException;
import com.chatbot.models.ChatResponse;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

public class ChatbotClient {
    private final String apiKey;
    private final String baseUrl;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;

    public ChatbotClient(String apiKey, String baseUrl) {
        this.apiKey = apiKey;
        this.baseUrl = (baseUrl != null ? baseUrl : "http://localhost:8000").replaceAll("/$", "");
        this.httpClient = HttpClient.newHttpClient();
        this.objectMapper = new ObjectMapper();
    }

    public ChatbotClient(String apiKey) {
        this(apiKey, "http://localhost:8000");
    }

    public ChatResponse chat(String message) throws Exception {
        return chat(message, "conv_" + UUID.randomUUID().toString().substring(0, 10));
    }

    public ChatResponse chat(String message, String conversationId) throws Exception {
        Map<String, Object> payload = new HashMap<>();
        payload.put("conversation_id", conversationId);
        payload.put("message", message);

        String jsonBody = objectMapper.writeValueAsString(payload);

        HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl + "/api/v1/chat"))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(jsonBody));

        if (apiKey != null && !apiKey.isEmpty()) {
            builder.header("X-API-Key", apiKey);
            builder.header("Authorization", "Bearer " + apiKey);
        }

        HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new ChatbotException("API returned error: " + response.body(), "API_ERROR", response.statusCode());
        }

        return objectMapper.readValue(response.body(), ChatResponse.class);
    }
}
