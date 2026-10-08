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

## restarting and revoking access

This trial keeps OAuth state and upstream tokens in memory. Restarting Mason invalidates
existing MCP tokens and client registrations, so reconnect the ChatGPT app. Restarting the
Quick Tunnel also changes the URL: update `.env`, the GitHub callback, and the ChatGPT URL.

To stop access immediately, stop Mason or revoke the Mason OAuth grant in GitHub's authorized
applications. A leaked Telegram session must also be revoked in Telegram's device settings.
For a service that stays on, add a stable hostname and encrypted persistent OAuth storage later.

## if something fails

- `401`: check owner ID, token expiry, and GitHub authorization; reconnect after a restart
- `429`: wait a minute; the HTTP limit includes invalid requests and OAuth calls
- `rate_limited`: wait for the Telegram retry interval shown in the tool error
- `chat_not_allowed`: choose a chat from the MCP `list_chats` tool
- `telegram_unavailable`: check the session, network, and chat access locally
- `invalid_cursor`: restart the search after changing its filters or allowed chats

Do not disable authentication to troubleshoot a public endpoint. Keep using demo data until
the connection works. Secret chats, attachment downloads, PDF content search, and photo search
are outside this first version.
