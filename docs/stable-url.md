# keeping the same address

Quick Tunnels were useful for the first connection, but changing the URL on every restart gets
old. Mason can also run with ngrok's assigned development domain. The free plan includes one
domain tied to the account, so there is no domain purchase for this option. See the current
[ngrok limits](https://ngrok.com/docs/pricing-limits/free-plan-limits) before relying on it.

The ngrok account still needs to be created, and the laptop still needs to be on. This is a
stable address for a local server, not always-on hosting.

## setup

1. Create an ngrok account and find its assigned HTTPS development domain in the dashboard
2. Install the agent from [ngrok's official download page](https://ngrok.com/download/linux)
3. Stop the separately running Mason server before changing its public URL
4. Enter the domain and authtoken locally:

```bash
uv run mason configure ngrok
```

The hidden prompts accept a hostname, HTTPS origin, or complete `/mcp` URL. The command saves
`MASON_PUBLIC_URL` and `MASON_NGROK_AUTHTOKEN` in the private `.env` file. It keeps the Telegram
session and allowed chats as they are. Do not paste the token into a chat or put it in shell
arguments.

Update the GitHub OAuth application's callback to the ngrok origin followed by `/auth/callback`,
then start both processes:

```bash
uv run mason start --tunnel ngrok
```

The command uses the configured address and passes the agent token through its environment.
HTTP traffic inspection is disabled, and raw tunnel output is discarded. Mason still checks
HTTPS, OAuth discovery, and refusal of anonymous requests before reporting readiness. Its own
OAuth remains required; an ngrok token is only for starting the tunnel.

Create a ChatGPT connection for the new MCP URL and sign in through GitHub. Uninstall the old
connection after the new one works. This is the same URL-change procedure described in
[the setup guide](setup.md). Stop the old Quick Tunnel once the new route is working.

## after that

Keep using `mason start --tunnel ngrok`. A normal restart uses the same development domain, so
the GitHub callback and ChatGPT MCP URL stay the same. Ctrl+C stops the server and agent.
The launcher's checks do not replace a real ChatGPT sign-in and tool-call test.

The free plan has request and transfer quotas. It also shows a notice for browser HTML pages;
ngrok documents that programmatic API requests are not affected. A browser visiting the OAuth
pages may need to acknowledge that notice. Paid plans and a Cloudflare Tunnel with a domain
are alternatives if the free limits become inconvenient.

To keep using the original temporary setup, run `mason start` without `--tunnel ngrok`. That
creates a new Cloudflare Quick Tunnel and updates the public URL again.
