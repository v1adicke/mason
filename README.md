# Mason

My little AI toolkit. Starting with Telegram search over MCP.

I want to ask ChatGPT where something was discussed, get the actual messages, and open the
source. Mason handles the Telegram side; ChatGPT handles the conversation.

The first version is read-only: keyword search, recent messages, and a bit of context around a
result. Semantic search and photos can wait until the basics work.

Built with Python, Telethon, and the official MCP SDK. One app, no extra search database yet.
