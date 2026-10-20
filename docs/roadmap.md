# what's next

Use existing apps and MCP servers first. Mason keeps the authenticated connection to
ChatGPT, while a local assistant handles voice and computer actions. Only write an
adapter when a real test shows that the ready-made options cannot do the job.

Linux is the current machine. The same setup should move to macOS without rebuilding
the assistant or the dashboard.

## first useful version

| Step | What should work |
| --- | --- |
| 1. Voice | Have a Russian conversation and hear an answer |
| 2. Browser | Open YouTube, read the signed-in recommendations, and explain the choices |
| 3. Playback | Pause, resume, skip, and change volume in a supported player |
| 4. Daily brief | Ask for recent news and get a short spoken answer with sources |
| 5. Home screen | Open a useful dashboard and switch to a world map |
| 6. Hands-free use | Try a wake phrase, interruptions, and music ducking |

OpenClaw is the first assistant candidate. It already supports MCP, browser tools,
and Talk mode. Use its browser UI for voice on Linux; the Linux desktop shell does
not provide microphone access. VoiceMode is an alternative if a separate speech MCP
fits the existing client better. Do not install both just to cover the same feature.

See [the setup notes](assistant-setup.md) for installation and verification status.

## current checklist

- [x] Keep the working Mason gateway and its existing integrations
- [x] Install a small Glance home dashboard on localhost
- [x] Verify weather and public news widgets in the browser
- [x] Keep the weather location in local settings rather than the shared config
- [x] Link World Monitor as a separate map, respecting its embedding restrictions
- [x] Install OpenClaw separately and connect its authenticated local UI
- [x] Open a public page through OpenClaw's dedicated browser
- [ ] Finish OpenClaw setup and verify one real model reply
- [ ] Verify Russian speech input and spoken output on the actual microphone and speakers
- [ ] Verify that the model can use browser tools for a requested task
- [ ] Read real YouTube recommendations after the owner signs in
- [ ] Test basic playback controls on a chosen player
- [ ] Test a spoken news brief with source links and timestamps
- [ ] Add a wake phrase after the manual voice loop works
- [ ] Check interruptions and background music with the actual audio devices
- [ ] Repeat the main checks on macOS

Installing a package is not proof that its voice or browser tools work. Keep the
untested items unchecked until the full action succeeds.

## music

Evaluate existing media tools before writing a player adapter. Spotify MCP servers
exist, but Spotify's developer policy prohibits voice-control assistants built on
its platform. Do not make that API the assumed voice-playback path. Start with local
player controls, then choose the music source separately.

## dashboard and macOS

Use Glance for weather, public feeds, and quick links. World Monitor provides the
world map and event layers. Its hosted MCP requires sign-in and has plan limits;
do not assume that the free dashboard includes unlimited data access.

On Linux, open the dashboard in the browser. On macOS, keep the same dashboard
configuration and consider Plash if a website directly on the desktop is useful.
Autostart and operating-system controls need their own macOS setup. Keep credentials
and browser profiles local; signing in again is part of the move.

## existing data sources

- Telegram uses the existing upstream through Mason; keep the built-in backend as a fallback
- Filesystem and Context7 already have isolated upstreams
- Discord's read-only bot integration is connected, but server history still needs a real test
- For Mail.ru, look for a maintained read-only integration before building an adapter
- Outlook mail is forwarded to Mail.ru, so a direct Outlook adapter is not needed

Phone access comes after the local workflow works. Reuse a suitable existing
assistant UI or remote-access tool before returning to a custom website.
The [older web app plan](web-app-plan.md) is deferred.

## references

- [OpenClaw](https://github.com/openclaw/openclaw)
- [OpenClaw Talk](https://docs.openclaw.ai/nodes/talk)
- [OpenClaw on Linux](https://docs.openclaw.ai/platforms/linux)
- [VoiceMode](https://github.com/mbailey/voicemode)
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)
- [World Monitor](https://github.com/koala73/worldmonitor)
- [World Monitor MCP](https://www.worldmonitor.app/docs/mcp-overview)
- [Glance](https://github.com/glanceapp/glance)
- [Plash](https://sindresorhus.com/plash)
- [Spotify developer policy](https://developer.spotify.com/policy)
