# what's next

Telegram is the first working module. The next goal is a web app I can use from my phone,
including remote control of my computer. Mail.ru and Discord follow as read-only
data sources. Keep each step useful on its own.

## order of work

| Step | What should work when it is done |
| --- | --- |
| 1. Web app | Sign in on the phone, search Telegram, save a query, and see the same state on the computer |
| 2. Computer control | Use the website for desktop access and a few quick controls, with separate access rules |
| 3. Email | Search and read Mail.ru, including forwarded mail, through Mason MCP and the website |
| 4. Discord | Use a suitable existing integration, or add a small bot adapter for selected channels |
| 5. Better search | Add a local text index only after actual searches show the need |

The implementation and security decisions are in [the web app plan](web-app-plan.md).
These are planned features; only the Telegram checklist below is already implemented.

## web app and computer control

- [ ] Build a responsive website using the existing Python app and service layer
- [ ] Add owner sign-in, browser sessions, device revocation, and shared saved queries
- [ ] Test Telegram search and state updates from both a phone and a computer
- [ ] Test desktop capture and keyboard/mouse input on the actual Hyprland session
- [ ] Integrate a browser desktop client and explicit control-session authorization
- [ ] Add allowlisted media, volume, and application controls
- [ ] Verify connection loss, session expiry, local stop, and refusal of unauthenticated control
- [ ] Add home-screen installation once the mobile website works

Full desktop access and quick controls are both in the target scope. Their order inside the
computer-control step can change after the first compatibility test and a choice of phone UX.
Computer control starts in the website; the current read-only MCP does not gain desktop rights.

## email

- [ ] Add shared mail models and read-only MCP tools with explicit account and folder access
- [ ] Connect Mail.ru with IMAP over TLS and an app password entered locally
- [ ] Add sender, subject, date, unread-status filters, pagination, and message reading
- [ ] Show the same mail results in the website
- [ ] Verify that reading preserves unread flags and that revoked access stops working

Outlook mail is already forwarded to the main Mail.ru inbox. Read those copies through Mail.ru;
a direct Outlook connection, Microsoft Graph app, and second mail adapter are outside this plan.
Mail.ru had no relevant match in the available plugin catalog. Account connection and allowed
folders still need to be configured separately; planning does not grant access to the inbox.

## Telegram

- [x] Keyword search, recent messages, and context around a result
- [x] OAuth, a chat allowlist, pagination, and bounded responses
- [x] Local login and setup checks
- [x] Start the server and a temporary tunnel together
- [x] Filter search by sender
- [x] Support an ngrok development domain in the launcher
- [x] Move the live connection to a stable address and test it from ChatGPT
- [x] Find documents using filenames and captions, without downloading files
- [x] Read a chosen date range without requiring search keywords

A local SQLite/FTS5 index can come after trying the keyword search in practice. Add embeddings
only if exact search and a text index still miss useful results. Photo search and voice can wait.

## Discord

The available plugin catalog did not return a relevant Discord integration. There are existing
open-source MCP servers, so evaluate them before writing another adapter. More plugins may be
available in the [plugin directory](https://chatgpt.com/plugins).

- [ ] Check a candidate's maintenance, license, bot authentication, transport, and actual tools
- [ ] Require server-enforced channel limits and an authenticated remote endpoint
- [ ] Verify real bot message-content access and keyword search in one selected channel
- [ ] Reuse a candidate if it fits; otherwise add a thin Python adapter to the official bot API
- [ ] Test channel discovery, search, recent messages, context, pagination, and access refusal

Use an official bot with access to explicitly chosen servers and channels. Neither a ready-made
server nor a bot invite replaces Mason's own channel allowlist.

Start with channel discovery, keyword search, recent messages, and neighboring context. Return
the author, timestamp, channel, message ID, and a link to the source. Reuse Mason's OAuth and
response limits, but keep Discord access rules separate from Telegram's chat allowlist.

The bot needs `VIEW_CHANNEL`, `READ_MESSAGE_HISTORY`, and message-content access for text search.
The [Discord message API](https://docs.discord.com/developers/resources/message#search-guild-messages)
documents native server search; test bot access, pagination, and index-not-ready responses with
one allowed channel before choosing a search implementation. Avoid a local archive unless it
solves a real problem.

This won't cover the owner's full personal DM history. Use the bot API, with no send, edit,
delete, or moderation tools. Regular user-account automation is outside this plan; see
[Discord's self-bot policy](https://support.discord.com/hc/en-us/articles/115002192352-Automated-User-Accounts-Self-Bots).
No Discord credentials or real channel data are needed while this is only a plan.
