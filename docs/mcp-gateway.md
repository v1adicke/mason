# gateway mode

Mason connects independent MCP servers to the existing ChatGPT app. It forwards their
schemas, annotations and results and prefixes each tool with its server name. It supports
stdio and Streamable HTTP. Sessions stay open for the lifetime of the HTTP application.

Set `MASON_MODE=gateway` in the private Mason environment file. The default configuration
path is `~/.config/mason/upstreams.json`; override it with `MASON_UPSTREAMS_FILE` if needed.
The file must belong to the current user, have permissions 600, and not be a symlink.

```json
{
  "mcpServers": {
    "example": {
      "command": "/absolute/path/to/server",
      "args": [],
      "read_only": true,
      "allow_writes": []
    },
    "remote": {
      "url": "https://example.org/mcp",
      "headers": {},
      "read_only": true
    }
  }
}
```

Use a command or URL for each server, never both. Stdio also supports `cwd` and `env`.
Keep credentials outside Git and load them in a private wrapper where possible.

`read_only` defaults to true. Mason then exposes only tools whose upstream annotation
explicitly says `readOnlyHint=true`, plus names explicitly included in `allow_writes`.
An unknown exception makes startup fail. These annotations are a filter, not a sandbox:
review each upstream before giving it account credentials or filesystem access.

The installed Telegram upstream is [chigwell/telegram-mcp](https://github.com/chigwell/telegram-mcp),
pinned to `6f169eacdd5582a291061ae15b4829029666f53c`. Its isolated runtime avoids conflicts
between its MCP SDK and Mason's SDK. The local wrapper loads the existing private
Telethon credentials and session and exposes 65 read tools and these six folder tools:

- `create_folder`
- `update_folder`
- `add_chat_to_folder`
- `remove_chat_from_folder`
- `delete_folder`
- `reorder_folders`

Telegram reads cover all cloud chats available to the account, without Mason's old chat
allowlist. Telegram secret chats are not available through Telethon. Message sending,
editing, deletion and mark-as-read tools are excluded. ChatGPT makes summaries from
the messages it reads; no additional OpenAI API key is needed.

Before changing folders, get a folder snapshot and preserve unrelated rules and pinned
chat order. Verify the result after the change. No real folder changes were made during
installation checks.

After editing the configuration, restart the service and refresh tools in the existing
Mason app's settings in ChatGPT. `uv run mason doctor --network` checks configuration,
public HTTPS, OAuth discovery and anonymous access refusal. It does not test an owner
tool call. The systemd service and ngrok tunnel currently run on the user's computer,
so that computer needs to stay on and connected. Independent 24/7 operation needs a
separate host.

## extra servers

The active configuration also includes:

- `filesystem`: official `@modelcontextprotocol/server-filesystem` 2.0.0, with ten
  read tools (including the compatibility alias `read_file`). Bubblewrap exposes
  only `Documents/homeworks` as `/projects/homeworks` and
  `Practice-Vladislav.Denyshev` as `/projects/c-linux`. Both mounts are read-only;
  the latter's `.git` directory is hidden. The process has no network namespace
  connected to the host and no access to the host's home directory or credentials.
- `context7`: official `@upstash/context7-mcp` 4.4.4, with two read tools. It runs
  over stdio in a separate filesystem sandbox with network access for public
  documentation queries. It has no coursework or credential mounts. Telemetry
  is disabled using `OTEL_SDK_DISABLED=true`. Do not send private code, file
  contents, account data or secrets as documentation queries.

Packages and their lockfile are in `~/.local/share/mason-mcp-extras`. The bundled
Node.js 24.19.0 executable was copied into its `bin/` directory so the services
do not depend on a shell's PATH. Installation scripts were disabled. The installed
dependency audit found no known vulnerabilities on 20 October 2026. Real reads,
path traversal refusal and write-tool refusal were verified before activation.

Discord's `mcp-discord-bridge` 1.2.0 is installed and checked in read-only mode;
its ten read tools and write refusal were verified without credentials. It is
not active until a Discord bot is authorized. `discord-upstream.json` and
`discord-launch.cjs` in the same private runtime directory prepare its sandbox.
The token mount is `~/.config/mason/discord-token`, permissions 600; the token
is read inside the sandbox and never included in process arguments. Add this
upstream to the active configuration only after validating the bot connection.
Discord uses a bot's server/channel access, not the personal account's full DMs.
The bundled search checks the most recent 100 channel messages; page through
history for older material instead of presenting it as complete history search.
