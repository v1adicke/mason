# Mason

My little AI toolkit. Starting with Telegram search over MCP.

I want to ask ChatGPT where something was discussed, get the actual messages, and open the
source. Mason handles the Telegram side; ChatGPT handles the conversation.

The first version is read-only: keyword search, recent messages, and a bit of context around a
result. Semantic search and photos can wait until the basics work.

Built with Python 3.12+, Telethon, and the official MCP SDK. One app, no extra search database yet.
FastMCP's OAuth bridge handles GitHub sign-in, so the first trial does not need a separate
identity-provider account.

## what it does

| Tool | Use it for |
| --- | --- |
| `list_chats` | Finding a chat by its title |
| `search_messages` | Keyword search with optional chat and date filters |
| `get_message_context` | Reading a result and the messages around it |
| `get_recent_messages` | Catching up on a few recent messages |

All remote reads stay inside an explicit chat allowlist. Results include the chat, author,
date, message ID, and a source link when Telegram supports one. If there is no link, Mason
returns the identifiers for manual lookup. It does not make one up.

## try it

```bash
uv sync
uv run pytest
```

The tests use fictional messages and generated test keys. They do not connect to Telegram.

For a real connection, follow [the setup guide](docs/setup.md): start a temporary HTTPS tunnel,
configure a GitHub OAuth app, test the demo from ChatGPT, then log into Telegram locally and
choose allowed chats.
There is no OpenAI API key involved in this setup.

```bash
uv run mason configure github
uv run mason configure telegram
uv run mason login
uv run mason chats
uv run mason serve
```

`uv run mason doctor --network` checks setup and public discovery without printing secrets.
The first trial uses a temporary URL and keeps OAuth state in memory, so server restarts need
a fresh connection from ChatGPT.

## a few things to know

Mason exposes read-only operations, but the Telegram session itself is a powerful credential.
Keep it outside the repo and do not share it. Requested message text is sent to ChatGPT when
a tool runs, so choose the allowed chats with that in mind.

Search uses Telegram's keyword search. It is not semantic search yet. Private message links
are limited, secret chats are out of scope, and the laptop has to be on for the server to work.

## working on it

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

The layout is small: `server.py` exposes the tools, `telegram/service.py` checks access and
search limits, and `telegram/client.py` talks to Telegram. More on the tradeoffs in
[the architecture notes](docs/architecture.md).

Next up: get the real connection working, see where keyword search falls short, then consider
a local text index.
