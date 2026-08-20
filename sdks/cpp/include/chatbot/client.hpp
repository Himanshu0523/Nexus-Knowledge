#ifndef CHATBOT_CLIENT_HPP
#define CHATBOT_CLIENT_HPP

#include "models.hpp"
#include <iostream>
#include <sstream>

namespace chatbot {

class ChatbotClient {
private:
    std::string api_key;
    std::string base_url;

public:
    ChatbotClient(const std::string& key, const std::string& url = "http://localhost:8000")
        : api_key(key), base_url(url) {}

    ChatResponse chat(const std::string& message, const std::string& conversation_id = "conv_cpp_default") {
        ChatResponse resp;
        resp.conversation_id = conversation_id;
        resp.message_id = "msg_cpp_mock";
        resp.text = "C++ SDK response to: " + message;
        resp.model = "qwen";
        return resp;
    }
};

} // namespace chatbot

#endif // CHATBOT_CLIENT_HPP
