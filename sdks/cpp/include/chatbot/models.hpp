#ifndef CHATBOT_MODELS_HPP
#define CHATBOT_MODELS_HPP

#include <string>
#include <vector>
#include <map>

namespace chatbot {

struct ChatResponse {
    std::string conversation_id;
    std::string message_id;
    std::string text;
    std::string model;
    int status_code = 200;
};

struct ChatRequest {
    std::string conversation_id;
    std::string message;
    std::string knowledge_base_id;
    std::map<std::string, std::string> metadata;
};

} // namespace chatbot

#endif // CHATBOT_MODELS_HPP
