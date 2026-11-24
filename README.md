<h1 align="center">bubblewise</h1>

<p align="center">
  <b>Let your AI agent text like a person on iMessage.</b><br>
  Real bold and italic instead of asterisks, effects for the moments that earn one, polls when people need to choose,<br>
  texts that arrive at the right time, and unsend for real mistakes. Over <a href="https://github.com/openclaw/imsg">imsg</a> or a <a href="https://bluebubbles.app">BlueBubbles</a> server.
</p>

<p align="center">
  <img alt="python" src="https://img.shields.io/badge/python-3.10%2B-3776ab">
  <img alt="dependencies" src="https://img.shields.io/badge/dependencies-none-30d158">
  <img alt="tests" src="https://img.shields.io/badge/tests-49-0a84ff">
  <img alt="license" src="https://img.shields.io/badge/license-MIT-8e8e93">
</p>

---

## The problem

Agents write markdown. iMessage does not render it. So an agent texting you either sends literal
`**asterisks**`, or its gateway strips them and every message arrives as flat grey text. It writes a
numbered list when it wants you to choose, says "I'll remind you" with no way to do it, and has no idea
that Messages can do any of the things people use every day.

Messages can do all of it natively. The tools to reach it exist ([imsg](https://github.com/openclaw/imsg),
BlueBubbles' Private API). What is missing is the layer in between: something that turns what an agent
naturally writes into native iMessage, and instructions that tell the agent when each feature fits.

## What it does

The agent writes ordinary text with two small markers. bubblewise sends it natively:

```text
Dinner moved to **7:30**, table for ~~4~~ 6. [[effect:confetti]]

See you there
```

arrives as two bubbles, `7:30` in real bold, `4` struck through, confetti on the screen. Preview it
without sending anything:

```bash
bubblewise preview "Dinner moved to **7:30**, table for ~~4~~ 6. [[effect:confetti]]"
```

```json
{
  "effect": "confetti",
  "bubbles": [{"text": "Dinner moved to 7:30, table for 4 6.",
               "ranges": [{"start": 16, "length": 4, "styles": ["bold"]},
                          {"start": 32, "length": 1, "styles": ["strikethrough"]}]}]
}
```

| You write | The person sees |
|---|---|
| `**bold**`, `*italic*`, `~~strike~~`, `<u>underline</u>` | real iMessage text styles |
| `[[effect:balloons]]` and 12 others | a bubble or screen effect |
| a blank line | a new bubble |
| `## headers`, tables, code fences | clean text, markup removed |
| `[label](https://url)` | the label, then a tappable link card |
| `[bloom]words[/bloom]` with `--text-effects` | animated words (imsg, once text effects ship there) |

And three commands for the rest:

```bash
bubblewise poll   --chat '<guid>' "Dinner Friday?" "Thai" "Pizza" "Somewhere new"
bubblewise later  --chat '<guid>' --at 07:30 "Leave by **8** for the airport"
bubblewise unsend --chat '<guid>' <message-guid>
bubblewise chats    # the chat GUIDs to use above
```

Where a backend has no route for a feature the message still goes: a poll on BlueBubbles becomes a numbered list, styles become
plain words, an effect is dropped. A server that rejects styled text gets the same text again, plain. Two
exceptions: invisible ink is never downgraded to plain text, since that would show the hidden words, and a
send that may have gone through is never sent twice.

## The skill

[`skills/bubblewise/SKILL.md`](skills/bubblewise/SKILL.md) is the part that makes an agent use this well.
It tells the agent how to shape a text (answer first, one idea per bubble), when to bold something (the one
thing you must not miss) and when not to, which effect fits which moment and when none does, when a
decision should be a poll, when a message should wait for the right time, and why unsend is for mistakes
rather than rewording.

## Wire it into your agent

Each agent reaches iMessage differently, so each has its own page:

- [Hermes Agent](docs/recipes/hermes.md): next to Hermes's BlueBubbles platform, for effects, Send Later and
  unsend.
- [OpenClaw](docs/recipes/openclaw.md): OpenClaw already sends styles, effects, polls and unsend through
  imsg; it takes the skill only.
- [Claude Code, Codex, or any agent with a shell](docs/recipes/any-agent.md): the CLI and the skill, over
  imsg on the same Mac.

Agents reading this repository can start at [llms.txt](llms.txt).

## Self-hosting, and doing it safely

An iMessage agent runs on a Mac signed in to an Apple ID, so setting one up is as much about security as
features. Two guides cover it:

- [docs/self-hosting.md](docs/self-hosting.md): choosing imsg or BlueBubbles, a dedicated macOS login and
  Apple ID for the agent, and standing the bridge up step by step.
- [docs/security.md](docs/security.md): what Full Disk Access and the Private API helpers expose, keeping
  the server off the public internet, passwords, who may text the agent and whom it may text, and what an
  agent must never do on someone's iMessage.

bubblewise enforces the outbound half: set `BUBBLEWISE_ALLOWED_CHATS` and it refuses every chat not on the
list, whatever the model asks for.

## Install

```bash
pipx install git+https://github.com/abhaymettu/bubblewise
```

Then point it at one backend:

```bash
# imsg (default): needs imsg on PATH, or IMSG_BIN
export BUBBLEWISE_BACKEND=imsg

# BlueBubbles
export BLUEBUBBLES_URL=http://localhost:1234
export BLUEBUBBLES_PASSWORD=...   # or BUBBLEWISE_BLUEBUBBLES_PASSWORD, for gateways that hide the shared name
```

## What needs what

Native iMessage features go through a helper inside Messages.app. Both backends' helpers need System
Integrity Protection partly disabled on the Mac that sends; see each project's docs.

| Feature | imsg | BlueBubbles |
|---|---|---|
| Plain text, bubbles, links | yes | yes |
| Bold, italic, underline, strikethrough | helper, macOS 15+ | Private API helper, macOS 15+, and a server release that forwards `textFormatting` to the helper. Current releases accept it and deliver plain text |
| Bubble and screen effects | helper | Private API helper |
| Animated text effects | an imsg release with text effects (proposed upstream) | no |
| Polls | helper | no; sent as a numbered list |
| Send Later | an imsg release with `--send-at` (proposed upstream), macOS 15+; Messages holds the text | the server's scheduler: plain text, the server must be running at that time |
| Unsend | helper, macOS 13+ | Private API helper, macOS 13+ |

The person receiving needs iOS 18, iPadOS 18 or macOS 15 to see text styles and animated text; older
devices show the words plain.

## How it works

`markup.parse` turns the agent's text into bubbles. Emphasis spans are wrapped in private-use characters,
the markdown that cannot render is stripped, and each bubble is walked once to produce its plain text and
its style ranges, counted in UTF-16 units the way Messages and BlueBubbles count them (an emoji is two). A
span that crosses a bubble break stays styled on both sides. The effect marker is pulled out first and
mapped to Messages' identifier (`balloons` is `com.apple.messages.effect.CKHappyBirthdayEffect`).

The two backends take the same parsed message. `Imsg` calls `imsg send-rich`, `imsg poll send` and
`imsg unsend`. `BlueBubbles` posts to `/api/v1/message/text` with `textFormatting` and `effectId`, and to
the unsend and schedule routes. No dependencies beyond the Python standard library.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

Tests run on fakes; nothing is sent. See [AGENTS.md](AGENTS.md).

## License

MIT
