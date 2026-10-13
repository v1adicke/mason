# getting it connected

For the first real test, I use a temporary Cloudflare URL and sign in through GitHub.
No domain purchase or separate identity-provider account is needed. The endpoint still
requires OAuth, including in demo mode.

## 1. local environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone git@github.com:v1adicke/mason.git
cd mason
uv sync
cp .env.example .env
chmod 600 .env
```

Keep `MASON_MODE=demo` while checking the connection. All demo messages are fictional.

## 2. a temporary HTTPS address

Install [cloudflared](https://github.com/cloudflare/cloudflared/releases), then keep this
running in a separate terminal:

```bash
cloudflared tunnel --url http://127.0.0.1:8000 --protocol http2 --no-autoupdate
```

Copy the generated `https://something.trycloudflare.com` address into `.env`, with `/mcp`:

```dotenv
MASON_PUBLIC_URL=https://something.trycloudflare.com/mcp
```

The server can start after the OAuth credentials are ready. Until then the tunnel has nothing
to forward to. Keep this same tunnel running throughout setup.

Quick Tunnels change hostname on restart and have no uptime guarantee. They also do not
support SSE; Mason uses Streamable HTTP with JSON responses for this trial. A stable hostname
can come later. See [Cloudflare's limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).

## 3. a GitHub OAuth app

Open [GitHub OAuth Apps](https://github.com/settings/developers) and create an app:

| Field | Value |
| --- | --- |
| Application name | Mason |
| Homepage URL | The Mason repository URL |
| Callback / redirect URI | The tunnel origin followed by `/auth/callback` |

Use the exact callback, without wildcard matching. Keep access-token expiration enabled and
device flow disabled. Generate a client secret on GitHub, then enter credentials locally:

```bash
uv run mason configure github
```

The prompts hide the client ID and secret. The owner ID is the numeric GitHub user ID, not
the username. It is available from the public profile API at
`https://api.github.com/users/YOUR_USERNAME`. If the local file already has the right ID,
leave that prompt empty to keep it.

Mason requests `read:user` for identity verification. It does not request repository write,
email-address, or profile-write scopes. A valid login from another GitHub account still cannot
read the owner's Telegram. See [GitHub's scope definitions](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps).

The [FastMCP GitHub OAuth bridge](https://gofastmcp.com/integrations/github) handles the OAuth
flow. Client registration is limited to known ChatGPT callbacks and local loopback clients.
The proxy consent screen stays enabled, and PKCE is required. Mason validates its own proxy
token and then verifies the owner through GitHub; a GitHub token alone is not an MCP token.

## 4. check the demo from ChatGPT

Start Mason and check the public connection:

```bash
uv run mason serve
```

In another terminal:

```bash
uv run mason doctor --network
```

The check validates the local settings, HTTPS endpoint, OAuth discovery, PKCE advertisement,
and refusal of anonymous MCP requests. It prints no credentials or conversations. Passing it
does not replace the actual sign-in and tool-call test.

In ChatGPT, open Plugins, use Add → Add custom MCP server, and enter the name and MCP URL.
Choose OAuth. Advanced OAuth settings should discover Dynamic Client Registration (DCR)
and the `read:user` scope. The GitHub app credentials belong only in Mason's local environment
file; they are not ChatGPT client credentials. Create the personal plugin, continue to Mason,
approve the proxy consent page, then sign in to GitHub as the configured owner.

Try:

> Search the Mason demo chat for "maths", then read the context around a result.

Check that results are labeled as fictional demo data. Confirm both search and context work
before enabling Telegram. Follow [OpenAI's connection guide](https://developers.openai.com/api/docs/guides/custom-mcp-server)
if the current ChatGPT UI differs.

## 5. Telegram, locally

Get API credentials from [my.telegram.org](https://my.telegram.org). Enter them through hidden
local prompts, then log in:

```bash
uv run mason configure telegram
uv run mason login
uv run mason chats
```

Do not paste API credentials, login codes, passwords, or sessions into a model chat. The default
session lives at `~/.local/share/mason/telegram.session`. The directory must have permissions
`700`, and session files must have permissions `600`. Mason checks ownership and permissions.

The local `chats` command prints dialog IDs and titles. Choose a few and update `.env`:

```dotenv
MASON_MODE=telegram
MASON_ALLOWED_CHATS=[-1001234567890,123456789]
```

Replace those placeholder IDs with real IDs from the local command. Restart Mason, reconnect
the ChatGPT app if needed, and search for a message I can verify manually. Compare the author,
date, text, and context against Telegram. Stop the server before repeating local session setup.

Mason labels the owner's self-chat as `Saved Messages (Избранное)`, so title search can find
it by either name instead of the owner's profile name.

## search filters

Read current pinned messages with `get_pinned_messages`. The fictional demo has one pinned
document message:

```json
{"chat_id": -1001234567890, "limit": 10}
```

The result is a normal message page, with `pinned: true` on each message. Results use the
original message date for ordering. To continue, pass `next_cursor` to the same tool and chat.
Pinned and recent-message cursors are separate. Messages can be unpinned while paging, so an
empty later page is possible. Use `get_message` or `get_message_context` to open a result.

Use `get_message` to open an ID from a search result. The fictional demo message with ID `2`
can be read like this:

```json
{"chat_id": -1001234567890, "message_id": 2, "text_limit": 1000}
```

The response has a `message`, `text_offset`, `total_text_length`, and `next_text_offset`.
If the next offset is present, call the same tool with that `text_offset` and the same chat
and message IDs. It reads up to 2,000 characters per call. Each call checks access again;
an offset does not grant access to another message. Compare `edited_at` between chunks and
start from zero if the message changed. Reading does not mark the message as read.

For parent replies, use `get_reply_chain`. The demo message `4` replies to `2`, which replies
to `1`; message `3` is unrelated:

```json
{"chat_id": -1001234567890, "message_id": 4, "limit": 10}
```

The result includes the starting message and its parents, oldest first. The limit counts
all returned messages, including the starting one. `stop_reason` is `end`, `limit`, `missing`,
`other_chat`, or `scheduled`. If there is a `next_message_id`, call the same tool with it in
the same chat and place that older page before the previous one. A missing parent has a
`missing_message_id`; it may have been deleted. Cross-chat and scheduled replies are not
followed. Search results now include `reply_to_chat_id` so a foreign reply ID cannot be
mistaken for an ID in the current chat.

For a supergroup's forward replies, use `get_thread_replies` with the root message ID:

```json
{"chat_id": -1001234567890, "message_id": 1, "limit": 1}
```

The demo returns message `4`, followed by `2` on the next page. Keep the same chat and root
when passing `next_cursor`. The root is excluded, and nested replies are included. Use the
`thread_root_message_id` from a known reply, or the parent chain, to find the root.
`get_message_context` continues to read chronological neighbors, which can include unrelated
messages.

Private chats, Saved Messages, and basic groups support parent-chain navigation but not this
thread-list tool. Broadcast-channel comments live in a separate discussion group; allow and
select that group explicitly, then use a root ID from that group. Mason does not resolve or
follow the channel-to-discussion-group mapping automatically. Thread pages are live reads;
deletion or editing can change later pages.

Use `get_unread_messages` to catch up without marking a chat as read:

```json
{"chat_id": -1001234567890, "limit": 10}
```

The demo has read messages through ID `2`, so this returns incoming messages `4` and `3`.
The response includes `read_inbox_max_id`, Telegram's live `unread_count`, and the separate
manual `unread_mark` badge. A manually marked chat can have zero unread messages; Mason does
not turn its whole history into unread results or clear that badge.

Continue with `next_cursor` and the same chat. Outgoing messages are skipped within a bounded
scan, so an empty page can still have a cursor. Reading in another Telegram client changes
the inbox marker and invalidates the old cursor; start again without it. New messages can
change the count while paging, and the count is not an exact size of the returned result set.
Forum and monoforum inboxes return `unsupported_unread` until per-topic markers are supported.
All reads keep the same chat allowlist and text limits.

For a request like "what was discussed yesterday?", use `get_recent_messages` with a chat ID
from `list_chats` and optional `date_from` and `date_to`. No keyword is needed. For example,
this reads the fictional demo chat for January 2 in a UTC+02:00 timezone:

```json
{
  "chat_id": -1001234567890,
  "date_from": "2026-01-02T00:00:00+02:00",
  "date_to": "2026-01-03T00:00:00+02:00",
  "limit": 20
}
```

The start is inclusive and the end is exclusive. Use the offset for the actual requested dates;
it can change with daylight saving time. Results stay newest first and use the configured
timezone. Continue with `next_cursor` and the same dates if the period has more messages.
The page is a bounded sample until paging is finished, so don't call it a complete recap yet.

`search_messages` accepts an optional `sender_id` from a returned message. For example, the
fictional demo sender has ID `1`:

```json
{"query": "maths", "sender_id": 1, "limit": 5}
```

For Telegram, use the actual `sender_id` returned by search, recent messages, or context.
It identifies the sender of the message; forwarded content may name a different original
author. Name lookup is not implemented yet. The filter combines with `chat_id`, `date_from`,
and `date_to`. Keep the sender and other filters the same when using a `next_cursor`.

Use `find_documents` for attachments. Its optional `query` uses Telegram's native text search;
`file_name` checks a case-insensitive substring of the displayed filename. Leave `query` out
when looking only by filename. Both filters can be combined with chat, date, and sender filters.

The demo has a fictional attachment called `discrete_maths.pdf`:

```json
{"file_name": ".pdf", "limit": 5}
```

Omit both filters to list recent documents. Results use the same message format, with
`file_name`, `mime_type`, and `file_size` in bytes when Telegram supplies them. No document is
downloaded, and captions or filenames do not tell Mason what is inside the file.

Filename matching checks at most `limit + 1` document messages per allowed chat on each call.
A page can be empty and still have a `next_cursor`; follow it with the same filters. This
keeps each request bounded while allowing older documents to be found without a local index.

Use `find_media` to find a particular kind of attachment in the allowed chats:

```json
{"media_type": "photo", "query": "trip", "limit": 5}
```

`media_type` is required: `photo`, `video`, `voice`, or `audio`. Leave out `query` to browse
that type without caption keywords. You can combine `chat_id`, `date_from`, `date_to`,
`sender_id`, and `file_name` just like in document lookup. A filename filter only matches
messages that actually have a filename; photos and voice notes often do not.

Results include the original message, `media_duration` in seconds, and `media_width` /
`media_height` in pixels when available. These fields can be null. Nothing is downloaded,
and the search does not inspect image contents or spoken words. Round video notes, GIFs,
and stickers are not part of these four search categories.

Keep all filters the same when following `next_cursor`, including the media type. Empty
pages can still have a continuation when a filename filter is used. The fictional demo
has a PDF but no photos, video, or audio, so its media search returns an empty page.

## restarting and revoking access

After the first setup, start both processes from one terminal:

```bash
uv run mason start
```

Stop any separately running Mason server and tunnel first. The command refuses a busy server
port, finds `cloudflared` on PATH or in `~/.local/bin`, and starts a new Quick Tunnel. It waits
for public HTTPS, OAuth discovery, and anonymous access refusal before saving the generated
MCP URL in the private `.env` file. If startup fails, the previous URL stays in the file.

Use the printed callback in the GitHub OAuth app and the printed MCP URL in ChatGPT. These
account settings still need updating manually. The check confirms server readiness, not that
the ChatGPT connection has already been updated. Ctrl+C stops both child processes; if either
process exits, Mason stops the other too. This command runs in the foreground, not as a service.
Raw server and tunnel output is suppressed, and the command prints only setup status and
public URLs. Use the separate `mason serve` and `cloudflared` commands above when diagnosing
a startup failure locally, without sharing raw output that might contain private data.

OAuth state and upstream tokens are encrypted in `~/.local/share/mason/oauth`, outside the
checkout. The directory must have permissions `700`; new files use `600`. Restarting Mason
keeps client registrations and token mappings. Changing the GitHub app secret makes the old
state unreadable and requires a fresh client registration. Restarting the Quick Tunnel changes
the URL: update `.env`, the GitHub callback, and the ChatGPT URL.

If ChatGPT does not let you edit the server URL, create a new custom MCP connection for the
new address and use OAuth with DCR again. Uninstall the old connection so it is not used in
new chats. Changing the tunnel address does not require another Telegram login.

To stop access immediately, stop Mason or revoke the Mason OAuth grant in GitHub's authorized
applications. A leaked Telegram session must also be revoked in Telegram's device settings.
For a service that stays on, add a stable hostname later. Treat the local OAuth directory and
environment file as credentials, and keep both out of Git and shared backups.

The [stable URL guide](stable-url.md) covers the optional ngrok account domain and
`mason start --tunnel ngrok`. The default `mason start` still uses a temporary Quick Tunnel.

## if something fails

- `401`: check owner ID, token expiry, and GitHub authorization; reconnect after a restart
- `429`: wait a minute; the HTTP limit includes invalid requests and OAuth calls
- `rate_limited`: wait for the Telegram retry interval shown in the tool error
- `chat_not_allowed`: choose a chat from the MCP `list_chats` tool
- `telegram_unavailable`: check the session, network, and chat access locally
- `invalid_cursor`: restart the search after changing its filters or allowed chats
- `unsupported_thread`: use parent-chain navigation, or select an allowed supergroup
- `unsupported_unread`: use normal history reads for topic-based chats until topic markers are supported

Do not disable authentication to troubleshoot a public endpoint. Keep using demo data until
the connection works. Secret chats, attachment downloads, PDF content search, image recognition,
and audio transcription are outside this first version.
