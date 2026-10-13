# Mason

My little AI toolkit. Starting with Telegram search over MCP.

I want to ask ChatGPT where something was discussed, get the actual messages, and open the
source. Mason handles the Telegram side; ChatGPT handles the conversation.

The first version is read-only: keyword search, document and media lookup, recent messages,
and a bit of context around a result. Semantic search and image recognition can wait.

Built with Python 3.12+, Telethon, and the official MCP SDK. One app, no extra search database yet.
FastMCP's OAuth bridge handles GitHub sign-in, so the first trial does not need a separate
identity-provider account.

## what it does

| Tool | Use it for |
| --- | --- |
| `list_chats` | Finding a chat by its title |
| `search_messages` | Keyword search with optional chat, date, and sender filters |
| `find_documents` | Finding attachments by caption keywords or part of their filename |
| `find_media` | Finding photos, videos, voice notes, or audio by type and caption |
| `get_message` | Reading a message by ID, including the rest of long text |
| `get_reply_chain` | Following the messages a result was replying to |
| `get_thread_replies` | Reading replies in a supergroup thread |
| `get_pinned_messages` | Reading the current pins in one allowed chat |
| `get_message_context` | Reading a result and the messages around it |
| `get_recent_messages` | Catching up on recent messages or reading a chosen date range |
| `get_unread_messages` | Reading incoming unread messages while keeping them unread |

All remote reads stay inside an explicit chat allowlist. Results include the chat, author,
date, message ID, and a source link when Telegram supports one. If there is no link, Mason
returns the identifiers for manual lookup. It does not make one up.

`get_message` reads a known message from an allowed chat. Search snippets are still limited
to 2,000 characters; use `next_text_offset` to read the rest in chunks. Keep the chat and
message ID the same, and check `edited_at` because Telegram messages can change between reads.

`get_reply_chain` follows parent replies in the same chat and returns up to 10 messages,
oldest first. It explains whether the chain ended, hit the limit, or reached an unavailable
parent. Use `next_message_id` to continue older parents. It stops at replies to another chat
or a scheduled message.

`get_thread_replies` reads replies in a supergroup, newest first, using the thread's root
message ID. Use `thread_root_message_id` from a result when available, or follow the parent
chain to find it. The root itself is not repeated in the reply pages. Nearby context is still
available separately; messages next to each other are not necessarily part of one discussion.
Channel comments in a linked group need that group to be allowed and selected explicitly.

Use `get_pinned_messages` with a chat ID from `list_chats`. It returns current pins newest
message first, with the same source metadata and text limits as search. Continue with
`next_cursor` to read older pins. Pinning and unpinning are not exposed as tools.

To search by sender, use the `sender_id` from a previous message result. The filter works with
dates and pagination, and it stays inside the same allowed chats.

To read a day or a week without searching for a word, use `get_recent_messages` with
`date_from` and `date_to`. Dates need a timezone offset. The start is included and the end
is excluded, so a full day runs from midnight to the next midnight. Keep the same dates
when following `next_cursor`.

`get_unread_messages` uses Telegram's current inbox read marker and leaves read status alone.
It skips outgoing messages. An empty page can still have a cursor, so keep paging. If I read
the chat in another client, the old cursor becomes invalid and I need to start again.
Forum and other topic-based inboxes need their own read markers and are not supported yet.

Document lookup returns the filename, MIME type, size in bytes, and the original message.
It reads metadata and captions; file contents stay in Telegram. An empty document page can
still have a `next_cursor`, so keep paging before deciding that nothing matched.

For media, choose `photo`, `video`, `voice`, or `audio`. Add caption keywords, a filename,
or chat, date, and sender filters when useful. Results include duration in seconds and image
dimensions when available. Photos and voice notes often have no filename. This finds the
original message; it does not download files, recognize pictures, or transcribe audio.

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

The priority is completing Telegram's read-only MCP tools. A website I can use from my phone,
with shared searches and computer control, comes after that.
Mail.ru and Discord are the next read-only data sources; forwarded Outlook mail comes through
the Mail.ru inbox. These are planned features; Telegram is what works today.
See [the roadmap](docs/roadmap.md) and
[the web app plan](docs/web-app-plan.md).
