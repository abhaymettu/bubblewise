# Self-hosting an iMessage agent

iMessage has no public API. Every self-hosted iMessage agent works the same way underneath: a Mac stays
signed in to an Apple ID, Messages.app runs on it, and a bridge reads Messages' database and drives the
app. Your agent talks to the bridge. This guide sets that up so it is useful and so it stays safe. Read
[security.md](security.md) before you give an agent the keys.

## What you need

- A Mac that stays on: a Mac mini, an old MacBook with the lid open, or a Mac in a hosted rack. Apple's
  license allows macOS only on Apple hardware.
- A dedicated macOS user account for the agent. Not your own login.
- A dedicated Apple ID for the agent, signed in to Messages in that account. People text the agent at that
  address, and the agent sees only that account's conversations.
- One bridge: imsg or BlueBubbles.

## Pick a bridge

| | [imsg](https://github.com/openclaw/imsg) | [BlueBubbles](https://bluebubbles.app) |
|---|---|---|
| What it is | A command-line tool and a JSON-RPC stream on the same Mac | A server app with a REST API and webhooks |
| Agent runs | On the same Mac | Anywhere that can reach the server |
| Reads messages | `imsg watch --json`, straight from the database | Webhooks pushed to your agent |
| Native features | Through its injected helper | Through its Private API helper |
| Good for | An agent on the Mac itself, fewest moving parts; OpenClaw's iMessage plugin uses it | An agent on another machine, or a gateway that already speaks BlueBubbles (Hermes Agent) |

Both helpers, the parts that send styles, effects, polls, replies and unsends, run inside Messages.app.
That requires turning System Integrity Protection partly off. Plain text sending and reading work without
it. See [security.md](security.md#sip-and-the-helpers) before you decide.

## Set up the Mac

1. Create a standard (not admin) macOS user for the agent, for example `agent`. Turn on automatic login
   for it only if the Mac sits somewhere physically safe.
2. Sign in to that user, open Messages, and sign in with the agent's Apple ID. Send yourself a test text
   from your phone and make sure it arrives.
3. Turn off sleep: System Settings, Energy, "Prevent automatic sleeping when the display is off".
4. Keep FileVault on and the macOS firewall on.

## Option A: imsg

1. Install imsg in the agent's user (see its [install guide](https://github.com/openclaw/imsg/blob/main/docs/install.md)).
2. Give Full Disk Access to the one program that runs imsg (the terminal, or the launch agent's binary),
   not to everything. System Settings, Privacy and Security, Full Disk Access.
3. Check: `imsg chats --json` lists the agent's chats. `imsg status --json` shows which advanced features
   the helper can use on this macOS version.
4. Optional, for native features: follow imsg's [Advanced IMCore](https://github.com/openclaw/imsg/blob/main/docs/advanced-imcore.md) guide to load its helper.
5. Run your agent in the same user. It reads with `imsg watch --json` and sends with `bubblewise`
   (`BUBBLEWISE_BACKEND=imsg`).

## Option B: BlueBubbles

1. Install BlueBubbles Server in the agent's user and follow its setup. Give it Full Disk Access and the
   Accessibility permission it asks for.
2. Set a long random server password (32 characters or more, from a password manager).
3. Keep the server on your own network. In its connection settings, use the local address or a private
   network such as Tailscale or WireGuard. Do not turn on a public proxy (Cloudflare, ngrok and similar
   options) unless you understand that the server is then on the public internet behind one password.
4. Optional, for native features: install the [Private API helper](https://docs.bluebubbles.app/helper-bundle/installation).
5. Point the agent at it: `BLUEBUBBLES_URL` and `BLUEBUBBLES_PASSWORD` in its environment, never in a
   file you commit. For incoming messages, register your agent's webhook in the server and check the
   password on every webhook request.
6. Check: `bubblewise chats` lists the agent's chats and their GUIDs; `bubblewise send --chat '<guid>'
   "TEST"` to your own chat reaches your phone.

## Then

- Set `BUBBLEWISE_ALLOWED_CHATS` to the chats your agent may send to (see [security.md](security.md#who-the-agent-may-text)).
- Give your agent [`skills/bubblewise/SKILL.md`](../skills/bubblewise/SKILL.md).
- After every macOS or Messages update, send yourself a test text. Helpers are the first thing an update
  breaks, and plain sending keeps working when they do.
