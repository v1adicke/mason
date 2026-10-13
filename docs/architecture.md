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

The optional `mason start` command supervises the server and a temporary `cloudflared` process.
It checks setup and the local port first, passes the generated public URL to the server, and
saves it only after checking the public endpoint. It does not change account settings on
GitHub or ChatGPT. Both child processes stop on interruption or when one of them exits.
The standalone `mason serve` command still works with an independently managed tunnel.

Only GitHub's `read:user` scope is requested. It identifies the caller; the Telegram allowlist
is a separate server-side policy. The proxy keeps consent and PKCE enabled, allows only known
ChatGPT callbacks and loopback clients, and encrypts OAuth state in `~/.local/share/mason/oauth`.
The encryption key is derived from the GitHub app secret using the library's key derivation.
The directory is private, and files are created with permissions `600`. Restarting Mason keeps
client registrations and token mappings. GitHub tokens and the app secret never go to ChatGPT.

There is one owner and one Telegram session. A valid token from another user still gets
rejected. There is no public signup in Mason and no login-code tool.

## the boundaries that matter

- All ten tools only read. No generic RPC, shell command, send, delete, download, or mark-read tool
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

Pinned-message reads use Telegram's native pinned filter in one allowed chat. Each call asks
for at most `limit + 1` messages, returns at most `limit`, and binds continuation to the same
chat and read type. The service rejects unpinned or foreign-chat results. The `pinned` flag
is also returned by normal reads when supplied by Telegram. Pins can change during pagination;
their order follows message date, and no pin-time ordering or snapshot is promised.

Document lookup uses Telegram's document filter, then checks the displayed filename locally
when `file_name` is supplied. Each call reads at most `limit + 1` document messages per chat.
Offsets advance over scanned documents that did not match, while preserving any matches that
did not fit on the returned page. Empty pages can have a continuation cursor. MIME type and
size come from message metadata, with no download or persistent file index.

Media lookup uses Telegram's native filters for
[photos](https://core.telegram.org/constructor/inputMessagesFilterPhotos),
[videos](https://core.telegram.org/constructor/inputMessagesFilterVideo),
[voice notes](https://core.telegram.org/constructor/inputMessagesFilterVoice), and
[audio](https://core.telegram.org/constructor/inputMessagesFilterMusic). The service checks
the returned media type and applies the same bounded filename scan as document lookup.
Each cursor binds the media type and all search filters. Durations and image dimensions
come from metadata. Link previews are not counted as attachments. Round video notes,
animations, and stickers have separate type labels in normal message reads; they are not
included in `find_media`'s four categories. There is no image recognition or transcription.

Across chats, each page merges bounded per-chat results. The cursor remembers the last
returned message in each chat. Telegram is live: deletion, editing, and new messages can affect
later pages. No snapshot or exact total count is promised.

Context reads actual messages before and after an anchor, rather than assuming IDs are dense.
`get_message` reads one explicit ID from the specified allowed chat. Long text can be continued
in chunks of at most 2,000 characters; the response includes total text length and the next
offset. Message reads check both the chat and returned ID. The backend also checks Telegram's
actual message peer before assigning a chat to a result. Text chunks are live reads, so an
edit or deletion can invalidate a continuation; compare `edited_at` and restart when it changes.
It is chronological neighboring context, not an entire reply thread. Private conversations and
basic groups have no invented message link. Channels and supergroups use supported Telegram
links; private links still require membership. Demo data has no real source links.
Telegram service events can have empty text and `kind=service`; they still count as real
neighbors and do not prematurely end a page.

Reply-chain reads fetch one parent at a time in the same chat, with at most 10 message reads
inside one 30-second operation. They return the oldest fetched parent first and a continuation
ID when more parents remain. Deleted parents produce a partial chain with `stop_reason=missing`.
Cross-chat and scheduled replies stop traversal even if the other chat is allowed. Cycles and
unexpected sources are rejected. The tools never treat a reply ID as an instruction to widen
the allowlist.

Thread pages use [Telegram's reply API](https://core.telegram.org/method/messages.getReplies)
in a specified supergroup. Channel posts can lead to a different discussion group, so this
tool rejects broadcast channels, private chats, and basic groups before reading replies.
The caller supplies a root ID; the service checks the root and each reply's chat and thread
metadata. Each page reads at most `limit + 1` replies, excludes the root, and binds its cursor
to the chat and root ID. Nested replies stay in the same
[Telegram thread](https://core.telegram.org/api/threads). Results are ordered by message ID,
newest first. No thread is marked as read, and no private-chat history scan is used to guess
which messages might be replies.

## planned web app and new services

The next version adds a phone-friendly website as a second interface to the same service
methods. Browser sessions have separate authorization from MCP. Small shared web state can
live in SQLite without introducing a message archive or a full-text index.

Mail.ru gets a read-only IMAP adapter so the website and MCP can use the same mail operations.
Forwarded Outlook mail is read from that inbox, without a direct Outlook connection.
Discord starts with an existing-integration check, then a bot adapter only
if needed. Each provider has its own explicit access policy.

Computer control uses a separately authorized web session and a local desktop process. It is
outside the current read-only MCP tools. Details, completion checks, and the order of work
are in [the web app plan](web-app-plan.md). These parts are not implemented yet.

SQLite/FTS5 search, embeddings, image recognition, voice control, and autonomous actions can
come later.
