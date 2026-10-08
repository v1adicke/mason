# getting it connected

The automated tests cover signed-token HTTP calls and a demo search. A real ChatGPT OAuth
connection and a real Telegram search still need to be checked with my own accounts.

## 1. local environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
git clone git@github.com:v1adicke/mason.git
cd mason
uv sync
cp .env.example .env
chmod 600 .env
```

Edit `.env` locally. Keep `MASON_MODE=demo` for the first connection test. Demo mode still
requires OAuth; it just removes the need for Telegram credentials.

## 2. OAuth provider

Use a provider that supports authorization code + PKCE, MCP discovery, and resource-bound
RS256 access tokens. Auth0 is one option. This is a setup example, not a completed deployment.

For Auth0, configure a dedicated API with:

- Identifier: the exact `MASON_PUBLIC_URL`, including `/mcp`
- Signing algorithm: RS256
- Permission: `telegram:read`, assigned to my user
- Resource Parameter Compatibility Profile enabled so MCP's `resource` selects the API audience

Register ChatGPT as an OAuth application using predefined client credentials. Copy the exact
callback URL shown in ChatGPT into the provider's allowed callbacks, enable authorization code
with PKCE, and allow that application to request the API permission. With predefined client
credentials, there is no need for open dynamic client registration.

Set these local values:

```dotenv
MASON_PUBLIC_URL=https://your-domain.example/mcp
MASON_OAUTH_ISSUER=https://your-tenant.auth0.com/
MASON_OAUTH_JWKS_URL=https://your-tenant.auth0.com/.well-known/jwks.json
MASON_OAUTH_OWNER=your-exact-auth0-user-id
```

Copy the issuer exactly as published in the provider's discovery document. The owner is its
user ID / token `sub`, not an email address. The provider must issue `telegram:read` in `scope`
and the exact public URL in `aud`. ID tokens and machine-to-machine tokens are not a substitute
for the owner's access token. Use a short access-token lifetime; revocation may otherwise take
effect only when an already-issued JWT expires. Refresh tokens stay with the OAuth client.

See [OpenAI's authentication guide](https://developers.openai.com/plugins/build/auth) and
[Auth0's MCP configuration example](https://auth0.com/blog/secure-csharp-mcp-server-with-auth0/).

## 3. HTTPS and a demo call

Start Mason:

```bash
uv run mason serve
```

Point a named Cloudflare Tunnel at `http://127.0.0.1:8000` using the same public hostname as
`MASON_PUBLIC_URL`. Keep the hostname stable: changing it also changes the OAuth resource and
requires updating the provider configuration. The laptop and tunnel must stay running.

The tunnel provides HTTPS, not user authentication. A separate browser-only Cloudflare Access
login in front of `/mcp` would need its own compatibility check; it is not the OAuth setup here.

Check the public endpoint without credentials:

```bash
curl -i -X POST https://your-domain.example/mcp \
  -H 'Content-Type: application/json' -d '{}'
```

Expect `401` and a `WWW-Authenticate` header pointing to resource metadata. Discovery lives at
`/.well-known/oauth-protected-resource/mcp`. `/health` returns a small public status response.

In ChatGPT, add the custom MCP URL, select OAuth, and enter the registered OAuth client
credentials in its settings. Sign in as the configured owner. Try:

> Search the Mason demo chat for "maths", then read the context around a result.

The result must say it is fictional demo data. Verify search and context both work before
enabling Telegram. ChatGPT UI availability and provider compatibility need this real test.

## 4. Telegram, locally

Get API credentials from [my.telegram.org](https://my.telegram.org). Put them into the local
`.env`; never paste credentials, login codes, passwords, or sessions into a model chat.

```bash
uv run mason login
uv run mason chats
```

Login prompts run in the local terminal and hide entered values. The default session location
is `~/.local/share/mason/telegram.session`. Its directory must have permissions `700`, and
session files must have permissions `600`. An existing insecure directory or file is rejected.

The `chats` command lists account dialog IDs and titles locally. Choose a few and configure:

```dotenv
MASON_MODE=telegram
MASON_ALLOWED_CHATS=[-1001234567890,123456789]
```

These IDs are placeholders; replace them with the actual IDs from the local command. Restart
Mason, refresh the ChatGPT tools if needed, then search for a message I can verify manually.
Read its context and compare the author, date, text, and source against Telegram.

Secret chats are outside this MVP. No attachments are downloaded. Document names and captions
may appear as metadata; searching PDF contents and searching photos are future work.

## if something fails

- `401`: check signature keys, issuer, owner ID, audience, expiry, and scope
- `429`: wait a minute; the HTTP limit includes invalid requests
- `rate_limited`: wait for the Telegram retry interval shown in the tool error
- `chat_not_allowed`: use an ID returned by the MCP `list_chats` tool
- `telegram_unavailable`: check the session, network, and current Telegram chat access locally
- `invalid_cursor`: restart the search after changing its filters or allowed chats

Do not turn authentication off to troubleshoot a public endpoint. Keep testing with demo data
until the connection works.
