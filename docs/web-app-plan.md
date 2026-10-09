# Mason on my phone

Mason now needs a real web app as well as MCP. I want to open a website on my phone, use the
same searches and settings as on my computer, and control that computer when needed.
Mail.ru and Discord should also be readable through MCP. Outlook mail already reaches the
main Mail.ru inbox through forwarding, so it does not need a direct connection. This describes
the next steps; the Mail.ru and Discord connections are not implemented yet.

## one backend, two ways to use it

Keep Python and the current service boundaries. Add web routes to the existing Starlette app,
server-rendered templates, responsive CSS, and small amounts of JavaScript. A separate React
app, message broker, and distributed job system are not needed for the first version.

```text
phone / computer browser -> web routes -> Telegram / mail / Discord services
ChatGPT or another client -> MCP routes -> the same read services

phone browser -> authorized control session -> local desktop agent
```

The website calls service methods directly. It does not call ChatGPT to perform a search, and
it does not copy business rules out of the services. MCP stays available at its current path.
The phone talks to the computer's server over HTTPS; it does not need a native phone app.

For the first slice, the computer hosts the website and data adapters. If it is off, the page
must clearly report that it is unavailable. Moving the web backend to an always-on host can
come later; the desktop agent would then connect outward with a separately revocable credential.

## what sync means first

Start with one owner, one computer, and a phone:

- A dashboard with connection status and links to search and computer control
- Telegram chat selection, keyword/date filters, results, context, and source links
- Saved queries and display preferences shared between browser sessions
- A device/session list with logout and revocation
- Visible refresh and connection errors, rather than a misleading offline success state

Use a small private SQLite database for web sessions, saved queries, and preferences. This is
application state, not a Telegram archive or search index. Save result references only if the
owner chooses to bookmark them; recheck access before reopening a reference. Revoking source
access must also prevent a bookmark from exposing its contents.

Short polling and normal requests are enough for dashboard updates at first. Add WebSockets
where interactive desktop access actually needs them. A PWA manifest and home-screen install
can follow. Cache public static assets only; private messages, tokens, and screen frames must
not enter a service-worker cache. Automatic file, clipboard, or phone-photo sync is a later,
separately enabled feature.

Done means a query saved on the phone appears on the computer after refresh, Telegram search
works on both, and a revoked browser session can no longer read either web API or live updates.

## controlling the computer

There are two useful interfaces: quick buttons for media/volume/selected applications, and
the actual desktop with keyboard and mouse input. Both belong in the target plan. Choose
which to deliver first after checking the desktop backend and the preferred phone interface.

Reuse a screen transport rather than write a video codec or remote-desktop protocol.
[noVNC](https://github.com/novnc/noVNC) is a browser-client candidate with mobile input support;
it still needs a working desktop server and a protected WebSocket bridge.
[Apache Guacamole](https://guacamole.apache.org/doc/gug/guacamole-architecture.html) is another
option if its extra gateway components solve a real compatibility problem.

First run a local compatibility test for the actual Wayland/Hyprland session: capture an
existing display, send keyboard and pointer input, and test resizing, locking, and disconnects.
[wayvnc](https://github.com/any1/wayvnc) is a candidate, not a promised working Hyprland backend.
A separate virtual desktop would not satisfy the goal of controlling the current computer.

Run desktop operations in a separate user process with a narrow local interface. Quick actions
have fixed names and validated arguments, such as a volume level or an application alias.
Do not expose an arbitrary shell-command endpoint or accept executable paths from the phone.
Process separation keeps desktop operations out of the MCP request handler; it is not a
sandbox against another process running as the same Linux user.

Remote desktop requires an explicit control session, including screen-view access. Pairing a
new phone should require confirmation on the computer. Let an already paired phone start a
short control session after fresh authentication, without requiring someone at the keyboard
every time. Show an active-control indicator and provide a local stop button and remote
disconnect. Stop accepting input immediately on disconnect, expiry, or revocation. Never replay
old clicks or queue a shutdown to run when the computer comes back online.

Clipboard sharing and file transfer start disabled. Shutdown/restart buttons require a clear
confirmation and short expiry; ordinary mouse events do not need a confirmation per click.
The computer must be on, connected, and running a compatible desktop session. Wake-on-LAN is
a later experiment, not something the website can promise over any network.

Done means touch input works on a real phone, read-only sessions cannot control anything,
unpaired devices are refused, and local stop or lost connectivity immediately ends control.

## web and MCP permissions

Reuse the existing owner identity check, but give browser login its own OAuth callback and
server-side session. The current MCP GitHub `read:user` scope identifies the owner; it is not
a desktop-control permission. MCP tokens cannot be used as browser control tickets.

Browser sessions use opaque cookies with `Secure`, `HttpOnly`, and `SameSite` protections.
Validate OAuth state, expiry, CSRF tokens for changes, and Origin on WebSocket connections.
Keep source access, device pairing, and desktop control as separate server-checked capabilities.
Do not store provider tokens or app passwords in browser storage or put them in URLs.

Authorize the WebSocket handshake and enforce expiry/revocation while it is connected. Only
the configured local desktop target is reachable; a caller cannot choose an arbitrary host
or port. VNC and agent ports stay private. Keep a bounded local action audit with action type,
time, device reference, and outcome, without screen captures, keystrokes, clipboard text,
mail content, or credentials.

Use the current HTTPS tunnel for the web prototype. Check streaming support and quotas before
using it for desktop sessions. The [ngrok free-plan limits](https://ngrok.com/docs/pricing-limits/free-plan-limits)
include a transfer quota, so repeated screen streaming may need a different private route or
hosting plan. Make that decision from a short measured session; no paid service is required
or purchased by this plan.

## Mail.ru, including forwarded mail

Build one small mail service backed by Mail.ru IMAP, with shared results: account, folder,
sender, subject, received time, bounded text, message reference, and a source link where the
provider supplies one. Expose proposed tools such as `mail_list_accounts`, `mail_list_folders`,
`mail_search`, and `mail_get_message` through MCP, and use the same service from the website.

Each call must name an allowed account. Folders have their own allowlist. Start with search by
sender, subject, dates, and unread status, then read a selected message. Return at most 50
items per page with bounded body text and an opaque cursor bound to account, folder, and
filters. Reading preserves flags. Attachments return metadata only; thread lookup can be
added later with honest partial-coverage reporting.

Mail.ru uses [IMAP over TLS and an app password](https://help.mail.ru/mail/login/mailer/).
Check that external-app access is available on the actual account before setup. Enter its
app password locally, not into ChatGPT. Select folders read-only and fetch with `BODY.PEEK`
so reading does not set the seen flag. Use UIDs together with folder `UIDVALIDITY`, not unstable
sequence numbers. Put bounds on server searches, MIME parsing, and decoded body size.

Outlook forwarding is already configured outside Mason. Search the delivered copies in Mail.ru,
using their actual headers and received times. Source links and message references belong to
the Mail.ru copy. Do not assume forwarding preserved the original sender, date, thread identity,
attachments, or all historical mail; check a chosen example when implementing. Mason does not
log in to Outlook, change forwarding, or register a Microsoft Graph app. A second mail backend
can wait until there is a real need.

The mail credential stays encrypted on the server, separate from browser
sessions. Mail HTML becomes bounded plain text for MCP; the website escapes displayed content
and does not load remote images or run email HTML. Mail text is untrusted data and cannot
authorize computer actions. No sending, deletion, moving, or automatic read-status changes.

Done means the permitted Mail.ru account can be searched and read through the web API and
authenticated MCP, a selected forwarded message is found in that inbox, flags stay unchanged,
forbidden accounts/folders are refused, and revoking credentials produces a safe error without
leaking provider responses.

## Discord: check reuse before writing

There was no relevant match in the available plugin catalog. That is not proof that no plugin
exists anywhere; check the [directory](https://chatgpt.com/plugins) again when implementing.
Existing open-source MCP servers are also candidates, not an automatic installation decision.

For example, [discord-readonly-mcp](https://github.com/Vorakorn1001/discord-readonly-mcp) offers
message/history reads over stdio, but does not advertise keyword search or Mason's authenticated
HTTP transport and channel policy. Verify the actual code and maintenance before reuse. Its
README's message-content-intent claim must be checked against the
[Discord message documentation](https://docs.discord.com/developers/resources/message), which
describes content restrictions and native guild search. Never rely on a README to grant access.

Accept a ready-made integration only if it can enforce our selected channels, keep write tools
unavailable, handle bot content permissions and rate limits, and fit authenticated remote MCP
without more work than a small Python adapter. Otherwise use the official bot API and reuse
Mason's existing service, auth, cursor, and response-limit patterns.

Start with allowed channel discovery, keyword search, recent messages, neighboring context,
and Discord source links. Test native guild search with a real bot, including channel filters,
pagination, and index-not-ready responses. If search is unavailable, offer a bounded scan with
an explicit coverage limit instead of pretending to search all history.

Bot access requires an invite and the relevant server/channel permissions. This covers selected
server channels, not the owner's full personal DM history. No user-account self-bot, message
sending, reactions, channel administration, or moderation tools in the first version.

## the next concrete slice

Implement owner web login, a mobile dashboard, Telegram search, and one shared saved query.
Test with fictional data first, then the existing authorized Saved Messages connection.
Alongside that, run a local desktop compatibility test before committing to a streaming stack.
Email and Discord get separate small steps after the web foundation and control boundary work.
Semantic indexing, voice, autonomous computer actions, and multi-user hosting remain later work.
