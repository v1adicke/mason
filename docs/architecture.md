# how it fits together

Mason starts as one Python process on my laptop. The MCP adapter knows about tool arguments
and responses. The Telegram service knows about allowed chats, pagination, and limits. The
Telethon backend knows how to read Telegram. The demo backend uses a few fictional messages
so I can test the connection before touching my account.

```text
ChatGPT -> HTTPS tunnel -> authenticated MCP -> Telegram service -> Telethon -> Telegram
```

The server binds to `127.0.0.1:8000`. A tunnel exposes `/mcp` over HTTPS. FastMCP's GitHub OAuth
proxy handles sign-in and client registration alongside the official SDK's MCP routes. It
issues signed reference tokens bound to the public `/mcp` URL, then validates upstream identity
through GitHub. Mason checks the signature, issuer, audience, expiry, and numeric owner ID.
OAuth discovery is public; Telegram tools are not.

Only GitHub's `read:user` scope is requested. It identifies the caller; the Telegram allowlist
is a separate server-side policy. The proxy keeps consent and PKCE enabled, allows only known
ChatGPT callbacks and loopback clients, and stores trial OAuth state in memory. After a restart,
reconnect the MCP app. GitHub tokens and the app secret never go to ChatGPT.

There is one owner and one Telegram session. A valid token from another user still gets
rejected. There is no public signup in Mason and no login-code tool.

## the boundaries that matter

- All four tools only read. No generic RPC, shell command, send, delete, download, or mark-read tool
- An explicit allowlist of 1–20 chats applies to every Telegram tool
- Searching without a chat checks each allowed chat separately, never Telegram's account-wide search
- At most 50 results per page and 10 neighbors per side of a context request
- Text is capped at 2,000 characters per message and 20,000 characters per response
- Pagination stores per-chat positions and binds them to the search; every page checks access again
- One Telegram operation at a time, a 30-second deadline, and no automatic FloodWait sleeping
- MCP and OAuth POST bodies are capped at 16 KiB; those endpoints share 60 requests per minute
- Sessions live outside the checkout in a private directory, with permissions checked at startup
- HTTP access logs are off; unexpected tool errors log only the exception type

Titles, names, captions, filenames, and message text are all untrusted source data. The tool
instructions tell the model to use them as evidence. The server's permissions do not depend
on whether the model follows that advice. Prompt injection can still influence a model's
answer or other connected tools, so these controls are not a complete model-side defense.

Read-only is a property of Mason's exposed operations. A stolen Telethon session still gives
access to the account. File permissions do not protect against another process running as me,
or against a compromised machine. Revoke a leaked session through Telegram's device settings.

Requested messages go to ChatGPT when a tool is called. There is no persistent message index
or media download, but that does not make the returned text local-only. Telethon's session
database also caches peer metadata; treat the whole file as sensitive.

## search details

Search uses Telegram's native keyword search. It is not semantic search. Results are sorted
newest first. `date_from` is inclusive and `date_to` is exclusive; both need a timezone offset.
Returned dates use the configured timezone.

Across chats, each page merges bounded per-chat results. The cursor remembers the last
returned message in each chat. Telegram is live: deletion, editing, and new messages can affect
later pages. No snapshot or exact total count is promised.

Context reads actual messages before and after an anchor, rather than assuming IDs are dense.
It is chronological neighboring context, not an entire reply thread. Private conversations and
basic groups have no invented message link. Channels and supergroups use supported Telegram
links; private links still require membership. Demo data has no real source links.
Telegram service events can have empty text and `kind=service`; they still count as real
neighbors and do not prematurely end a page.

SQLite/FTS5, embeddings, photo search, voice, and other modules can come later. They do not
need scaffolding in this version.
