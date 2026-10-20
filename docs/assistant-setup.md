# assistant setup

The assistant runs locally, alongside the existing Mason gateway. Installing it
does not replace the Telegram connection or automatically give it the same account access.

## home dashboard

Glance 0.8.7 runs at <http://127.0.0.1:8087/>. The release archive's SHA-256 was checked
against the digest published by GitHub. The dashboard listens only on the loopback
interface. Its weather and news widgets have been checked in the browser.

Shared files:

- `deploy/glance.yml`: theme, layout, public feeds, and links
- `deploy/mason-dashboard.service`: Linux user service
- `deploy/mason-home.desktop`: app-menu shortcut, with a world-map action

Local files:

- `~/.local/share/mason-dashboard/glance`: installed binary
- `~/.config/mason/glance.yml`: active dashboard configuration
- `~/.config/mason/dashboard.env`: weather location and timezone

Set `MASON_WEATHER_LOCATION` to a city and country in the local environment file.
The first trial uses Nicosia and `Asia/Nicosia`; change those if needed.
The calendar widget is a month view, not a connection to a personal calendar.
The assistant shortcut opens OpenClaw's local UI. Its Gateway runs as a separate user service.

```bash
install -m 600 deploy/glance.yml ~/.config/mason/glance.yml
install -m 644 deploy/mason-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user restart mason-dashboard
```

World Monitor opens separately. Its hosted site refuses third-party frames, so
there is no embedded map workaround. The hosted MCP is optional and needs a
World Monitor account; its free plan has a small daily allowance.

## voice assistant

OpenClaw 2026.10.5 is installed in an isolated directory under
`~/.local/share/mason-assistant`. The package archive's SHA-512 was checked against
the npm registry's integrity value. Dependency installation scripts were disabled;
OpenClaw's own package-local setup script was reviewed and run separately.

The local CLI is `~/.local/bin/openclaw`. The Gateway runs as the
`openclaw-gateway` user service at <http://127.0.0.1:18789/> with token authentication.
Its config and account state live in `~/.openclaw`, outside Git. The UI has been
connected, and its dedicated browser opened a public test page successfully.
That checks the browser controls, not a model's ability to choose and call them.

The initial tool profile allows browser actions and public web fetches. There is
no shell tool or automatic connection to Mason's private upstreams. Telemetry and
recurring agent heartbeats are disabled. The Linux service has a 2 GiB memory cap;
this is a limit, not a claim about normal usage.

Model authentication needs a separate OpenClaw sign-in. Reusing the existing native
Codex environment would also share its user configuration; that option was not enabled.
A real model reply, spoken conversation, and signed-in YouTube recommendations remain
unchecked until sign-in and live tests succeed.

Use the browser Talk interface on Linux. Check a real model reply before trying voice,
then test Russian recognition, spoken output, and interruptions with the actual audio
devices. A model login is not proof that the account can use the selected voice service.
Do not save or publish microphone recordings as test fixtures.

Test browser control with a public page first. YouTube recommendations require a
signed-in browser profile, so they remain unverified until that profile is connected.
Use a dedicated profile for the assistant and keep its session files local.

## moving to a Mac

Install the macOS versions of the chosen apps, copy the dashboard configuration,
and set the local weather location again. Reconnect accounts on the new machine.
Replace Linux autostart with the assistant's supported macOS service setup.
Plash is an optional wrapper for showing a website on the desktop.

The browser dashboard and MCP definitions can stay the same. Player controls,
microphone permissions, desktop automation, and startup need a fresh macOS check.
