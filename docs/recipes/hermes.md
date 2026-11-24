# bubblewise with Hermes Agent

Hermes already talks to iMessage through its built-in BlueBubbles platform. Out of the box its replies
arrive as plain text with the markdown stripped, and it cannot send an effect or unsend a message. This recipe adds
bubblewise next to that platform so the agent can send an effect, schedule a text and unsend a mistake, and
installs the skill that tells it when each one fits.

Read [../security.md](../security.md) first. An iMessage agent holds an Apple ID.

## Which bridge

**BlueBubbles.** It is the iMessage platform Hermes ships with, and bubblewise talks to the same server.

If your Hermes reaches iMessage through a third-party imsg plugin instead (for example
[hermes-imsg-cli](https://github.com/promptclickrun/hermes-imsg-cli)), that plugin already sends styled
text, effects, polls and unsends through its own tools. Install only the skill (step 3) for when to use each
one, and skip the rest.

## What works today

| Feature | Hermes alone | With bubblewise | Waits on |
|---|---|---|---|
| Plain replies | yes | unchanged, Hermes still sends them | |
| Bold, italic, strikethrough | stripped | sent, but current BlueBubbles server releases deliver them plain | [bluebubbles-server#907](https://github.com/BlueBubblesApp/bluebubbles-server/pull/907) (open) |
| Bubble and screen effects | no | yes, with the Private API helper | |
| Unsend | no | yes, with the Private API helper, macOS 13+ | |
| Send Later | no | yes, the server's scheduler, plain text, the server must be running then | |
| Polls | no | no, sent as a numbered list | no BlueBubbles route |

[hermes-agent#159758](https://github.com/NousResearch/hermes-agent/pull/159758) (open, not merged) adds text
styles, effects and unsend to Hermes's own BlueBubbles replies, with instructions for the agent. If it lands,
Hermes's replies carry styles, effects and unsend without bubblewise, and this recipe will change.

## Steps

**1. Get Hermes working on iMessage first.** Follow Hermes's
[BlueBubbles guide](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/bluebubbles) until the
agent answers a text from your phone. For effects and unsend, install the BlueBubbles
[Private API helper](https://docs.bluebubbles.app/helper-bundle/installation); the gateway log line
`connected to ... (private_api=True, helper=True)` shows it is up.

**2. Install the CLI where Hermes runs commands.** With the default local terminal, that is the machine
running the gateway. With a Docker, SSH or Modal terminal backend, install it inside that environment.

```bash
pipx install git+https://github.com/abhaymettu/bubblewise
bubblewise --version
```

**3. Install the skill.**

```bash
hermes skills install abhaymettu/bubblewise/skills/bubblewise
```

Hermes scans it, asks you to confirm, and puts it at `~/.hermes/skills/bubblewise/SKILL.md`. Copying that
folder there by hand works too.

**4. Give bubblewise its own copy of the server address and password.** Hermes deliberately strips
`BLUEBUBBLES_SERVER_URL` and `BLUEBUBBLES_PASSWORD` from the agent's shell and refuses to pass them through,
so bubblewise reads its own names for the same two values: `BLUEBUBBLES_URL` holds what
`BLUEBUBBLES_SERVER_URL` holds, and `BUBBLEWISE_BLUEBUBBLES_PASSWORD` holds what `BLUEBUBBLES_PASSWORD`
holds. First find your chat's GUID: install bubblewise in your own terminal too, export those two values
there, and run `bubblewise chats --limit 100`; it lists recent chats, their names and the people in them.
Then add to `~/.hermes/.env`:

```bash
BLUEBUBBLES_URL=http://192.168.1.10:1234
BUBBLEWISE_BLUEBUBBLES_PASSWORD=your-server-password
BUBBLEWISE_ALLOWED_CHATS="iMessage;-;+15555550123"
```

`BUBBLEWISE_ALLOWED_CHATS` lists the chats bubblewise may send to, comma-separated. Anything else is refused
before a request leaves the machine.

This puts the password where the agent's shell can read it, which is the thing Hermes was avoiding. If that
is not acceptable on your setup, stop here, keep Hermes's plain replies, and wait for #159758.

**5. Pass those names to the shell and let a bubblewise send stand alone.** In `~/.hermes/config.yaml`:

```yaml
terminal:
  env_passthrough:
    - BLUEBUBBLES_URL
    - BUBBLEWISE_BLUEBUBBLES_PASSWORD
    - BUBBLEWISE_ALLOWED_CHATS
platforms:
  bluebubbles:
    allow_silence: true
```

Hermes delivers the agent's reply to the chat. When the agent sends with bubblewise, the skill tells it to
answer `[SILENT]` so the person does not get the message twice. On a message from a person, Hermes replaces a
bare `[SILENT]` with a short notice unless `allow_silence` is on for the platform. If the agent answers
`[SILENT]` by mistake, that text now goes unanswered, which is the price of turning it on.

**6. The owner restarts the gateway**, not the agent, so the config change is read: `hermes gateway stop`
then `hermes gateway start` for the service, or stop and rerun `hermes gateway run`. An agent restarting
its own gateway cuts off the conversation it is in.

From then on the agent answers most texts with a normal reply, as before. It reaches for bubblewise for what
Hermes cannot send: an effect, a text at a set time, or an unsend of something it sent with bubblewise.
Hermes's own replies cannot be unsent this way.

## First test

1. In `hermes`, ask: *Run `bubblewise preview "Dinner at **7:30** [[effect:confetti]]"` and show me the
   output.* It prints JSON with `"effect": "confetti"`. Nothing is sent.
2. Ask: *Run `bubblewise chats`.* It lists your allowed chat. This proves the address and password reached
   the agent's shell.
3. From your phone, text the agent: *Send me a confetti text that says the setup works.* One bubble arrives,
   with confetti, and no second copy. If you also get a short notice, `allow_silence` is not on. If the
   output says `"plain": true`, the Private API helper is not connected.
4. If the agent says the chat is not in `BUBBLEWISE_ALLOWED_CHATS`, add the exact GUID from its error. If it
   says `set BLUEBUBBLES_URL and BLUEBUBBLES_PASSWORD`, the shell did not get step 4's names; check step 5
   and restart.

## Sources

Every key above is from Hermes's own docs or source (main, 2026-11-24): skills install and the
`~/.hermes/skills` layout (`website/docs/user-guide/features/skills.md`), BlueBubbles setup
(`website/docs/user-guide/messaging/bluebubbles.md`), `terminal.env_passthrough`
(`website/docs/developer-guide/creating-skills.md`), the shell's secret stripping
(`tools/environments/local.py`, `tools/env_passthrough.py`), and silence tokens and `allow_silence`
(`website/docs/user-guide/messaging/index.md`).
