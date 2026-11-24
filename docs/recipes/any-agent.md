# bubblewise with Claude Code, Codex or any agent with a shell

Any agent that can run a command can text through bubblewise, and any agent that reads `SKILL.md` files can
load the skill that says when to bold, add an effect, make a poll, schedule or unsend. A coding agent can
text you when a long job finishes, send a poll to a group you are in, or remind you at a time. These agents
do not read incoming texts by themselves; for an agent people text back and forth with, see the
[Hermes](hermes.md) and [OpenClaw](openclaw.md) recipes.

Read [../security.md](../security.md) first. An iMessage agent holds an Apple ID.

## Which bridge

**imsg, when the agent runs on the Mac signed in to Messages.** It runs without a server or a password,
so nothing secret sits in the agent's environment. **BlueBubbles, when the agent runs on another machine**,
since its server is reachable over the network; the agent's shell then holds the server password (see
security.md).

## What works today

| Feature | imsg | BlueBubbles | Waits on |
|---|---|---|---|
| Plain text, bubbles, links | yes | yes | |
| Bold, italic, underline, strikethrough | yes, helper, macOS 15+ | sent, delivered plain by current server releases | [bluebubbles-server#907](https://github.com/BlueBubblesApp/bluebubbles-server/pull/907) (open) |
| Bubble and screen effects | yes, helper | yes, Private API helper | |
| Polls | yes, helper | no, sent as a numbered list | |
| Unsend | yes, helper, macOS 13+ | yes, Private API helper, macOS 13+ | |
| Send Later | no | yes, the server's scheduler, plain text | [imsg#410](https://github.com/openclaw/imsg/pull/410) (open) for imsg |
| Animated words | no | no | [imsg#409](https://github.com/openclaw/imsg/pull/409) (open) |

"Helper" means the part of each bridge that runs inside Messages.app, which needs System Integrity
Protection partly off. See [../self-hosting.md](../self-hosting.md).

## Steps

**1. Stand up the bridge** with [../self-hosting.md](../self-hosting.md), and check it: `imsg chats --json`
lists chats, or the BlueBubbles server answers on its address.

**2. Install the CLI** on the machine where the agent runs commands:

```bash
pipx install git+https://github.com/abhaymettu/bubblewise
bubblewise --version
```

**3. Install the skill** where your agent looks for skills:

| Agent | Folder |
|---|---|
| Claude Code | `~/.claude/skills/bubblewise/` (all projects) or `.claude/skills/bubblewise/` (one repo) |
| Codex | `~/.agents/skills/bubblewise/` (all repos) or `.agents/skills/bubblewise/` (one repo) |
| Anything else that reads `SKILL.md` | that agent's skills folder, or paste the file into its instructions |

```bash
mkdir -p ~/.claude/skills/bubblewise
curl -fsSL https://raw.githubusercontent.com/abhaymettu/bubblewise/main/skills/bubblewise/SKILL.md \
  -o ~/.claude/skills/bubblewise/SKILL.md
```

Or let the [skills CLI](https://github.com/vercel-labs/skills) do it for one or more agents:

```bash
npx skills add abhaymettu/bubblewise -g -a claude-code -a codex
```

**4. Set the environment** in the shell profile the agent starts from (`~/.zshrc` on a Mac), then restart
the agent so it picks the values up. bubblewise uses imsg unless `BLUEBUBBLES_URL` is set:

```bash
# imsg (default)
export BUBBLEWISE_BACKEND=imsg
# or BlueBubbles
export BLUEBUBBLES_URL=http://192.168.1.10:1234
export BLUEBUBBLES_PASSWORD=...

# both: the only chats bubblewise may send to
export BUBBLEWISE_ALLOWED_CHATS='iMessage;-;+15555550123'
```

`bubblewise chats --limit 100` lists recent chats and their GUIDs; run it before you set the allowlist,
since it shows only allowed chats after. A group chat appears only if the agent's own Apple ID is in it. Keep the password out of any file a repository tracks.

## First test

1. `bubblewise preview "Dinner at **7:30** [[effect:confetti]]"` prints the bubble, the bold range and the
   effect. Nothing is sent.
2. Ask the agent: *Text me on iMessage that the setup works, with confetti.* It should load the skill, run
   `bubblewise send --json --chat '<your chat>'` with the text on stdin, and get back
   `{"sent": 1, "guids": [...], "effect": "confetti", "plain": false}`. One bubble arrives on your phone.
3. Ask it to send to a chat that is not on the list. It should refuse and tell you, not look for another way.

## Sources

Skill folders from each agent's docs (2026-11-24): Claude Code
[skills](https://code.claude.com/docs/en/skills) and Codex [skills](https://developers.openai.com/codex/skills).
The skills CLI's `-g` and `-a` flags and agent names are from its
[commands](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) and
[agents](https://github.com/vercel-labs/skills/blob/main/docs/agents.md) references.
