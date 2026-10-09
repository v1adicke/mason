# what's next

Telegram is the first working module. Keep changes small and useful before adding more services.

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

The next candidate is a small read-only Discord MCP module. Check for a maintained, compatible
integration before writing another adapter. If there isn't one that fits, use an official bot
with access to explicitly chosen servers and channels.

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
