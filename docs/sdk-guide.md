# Platform SDK Guide

This guide covers usage of official client libraries for Python, Node.js, Java, and C++.

---

## 1. Python SDK

```bash
pip install ./sdks/python
```

### Usage
```python
from chatbot_sdk import ChatbotClient

client = ChatbotClient(
    api_key="sk_dev_key_123456789",
    base_url="http://localhost:8000"
)

# Synchronous Chat
response = client.chat("Explain quantum mechanics")
print(response.text)

# SSE Streaming
for event in client.chat_stream("Explain machine learning"):
    if event.type == "token":
        print(event.content, end="", flush=True)
```

---

## 2. Node.js / TypeScript SDK

```bash
npm install ./sdks/node
```

### Usage
```typescript
import { ChatbotClient } from "@chatbot/sdk";

const client = new ChatbotClient({
  apiKey: "sk_dev_key_123456789",
  baseUrl: "http://localhost:8000"
});

async function main() {
  const response = await client.chat("Explain cloud computing");
  console.log(response.text);
}

main();
```

---

## 3. Java SDK

```java
import com.chatbot.ChatbotClient;
import com.chatbot.models.ChatResponse;

public class App {
    public static void main(String[] args) throws Exception {
        ChatbotClient client = new ChatbotClient("sk_dev_key_123456789", "http://localhost:8000");
        ChatResponse response = client.chat("Explain virtualization");
        System.out.println(response.getText());
    }
}
```

---

## 4. C++ Header-Only SDK

```cpp
#include "chatbot/client.hpp"
#include <iostream>

int main() {
    chatbot::ChatbotClient client("sk_dev_key_123456789", "http://localhost:8000");
    auto response = client.chat("Hello from C++!");
    std::cout << response.text << std::endl;
    return 0;
}
```
