# Mason

My little AI toolkit. Starting with Telegram search over MCP.

I want to ask ChatGPT where something was discussed, get the actual messages, and open the
source. Mason handles the Telegram side; ChatGPT handles the conversation.

The first version is read-only: keyword search, document lookup, recent messages, and a bit of
context around a result. Semantic search and photos can wait until the basics work.

Built with Python 3.12+, Telethon, and the official MCP SDK. One app, no extra search database yet.
FastMCP's OAuth bridge handles GitHub sign-in, so the first trial does not need a separate
identity-provider account.

## what it does

| Tool | Use it for |
| --- | --- |
| `list_chats` | Finding a chat by its title |
| `search_messages` | Keyword search with optional chat, date, and sender filters |
| `find_documents` | Finding attachments by caption keywords or part of their filename |
| `get_message_context` | Reading a result and the messages around it |
| `get_recent_messages` | Catching up on recent messages or reading a chosen date range |

All remote reads stay inside an explicit chat allowlist. Results include the chat, author,
date, message ID, and a source link when Telegram supports one. If there is no link, Mason
returns the identifiers for manual lookup. It does not make one up.

To search by sender, use the `sender_id` from a previous message result. The filter works with
dates and pagination, and it stays inside the same allowed chats.

To read a day or a week without searching for a word, use `get_recent_messages` with
`date_from` and `date_to`. Dates need a timezone offset. The start is included and the end
is excluded, so a full day runs from midnight to the next midnight. Keep the same dates
when following `next_cursor`.

Document lookup returns the filename, MIME type, size in bytes, and the original message.
It reads metadata and captions; file contents stay in Telegram. An empty document page can
still have a `next_cursor`, so keep paging before deciding that nothing matched.

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
The first trial uses a temporary URL. OAuth state is encrypted outside the repo, so restarting
Mason keeps the client registration. Restarting the tunnel still changes the public URL.

Once setup is done, `uv run mason start` runs the server and temporary tunnel together. It
checks the public endpoint, saves the new URL locally, and prints the callback to use on
GitHub. Ctrl+C stops both processes. The address still changes on each fresh tunnel, so the
ChatGPT connection needs updating too. `mason serve` stays available for a tunnel I run myself.

For a stable address, Mason also supports `mason start --tunnel ngrok` with the development
domain assigned to an ngrok account. Follow [the stable URL guide](docs/stable-url.md) for the
one-time setup. No domain purchase is needed for that option.

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

Next up: a website I can use from my phone, with shared searches and computer control.
Mail.ru and Discord are the next read-only data sources; forwarded Outlook mail comes through
the Mail.ru inbox. These are planned features; Telegram is what works today.
See [the roadmap](docs/roadmap.md) and
[the web app plan](docs/web-app-plan.md).
