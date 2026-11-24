# bubblewise with OpenClaw

OpenClaw already sends native iMessage. Its official iMessage plugin turns the agent's markdown into real
bold, italic, underline and strikethrough, and its message tool has actions for effects, polls, unsend,
edit and threaded replies. So OpenClaw does not need the bubblewise CLI. It gains the skill, which says when to
bold something, which effect fits which moment and when none does, when a decision should be a poll, and why
unsend is for mistakes.

Read [../security.md](../security.md) first. An iMessage agent holds an Apple ID.

## Which bridge

**imsg.** OpenClaw removed BlueBubbles support; iMessage now goes only through the `@openclaw/imessage`
plugin, which drives [imsg](https://github.com/openclaw/imsg) on the Mac signed in to Messages. An old
`channels.bluebubbles` block does nothing on current OpenClaw.

## What works today

| Feature | OpenClaw's iMessage plugin | Waits on |
|---|---|---|
| Bold, italic, underline, strikethrough | yes, from markdown; recipients on macOS 15 or iOS 18 and newer see the styles | |
| Bubble and screen effects | yes, message tool action `sendWithEffect`, Private API mode | |
| Polls | yes, action `poll`, Private API mode; recipients on iOS, iPadOS or macOS 26 and newer vote natively | |
| Unsend | yes, action `unsend`, only messages the gateway sent | |
| Send Later held by Messages | no | [imsg#410](https://github.com/openclaw/imsg/pull/410) (open) |
| Animated words | no | [imsg#409](https://github.com/openclaw/imsg/pull/409) (open), then an OpenClaw action to use it |

For a text at a set time today, use OpenClaw's own
[cron jobs](https://docs.openclaw.ai/automation/cron-jobs/delivery) with announce delivery to the chat.

bubblewise's outbound allowlist does not apply here, since OpenClaw sends. Limit who can reach the agent
with OpenClaw's own `channels.imessage.allowFrom`.

## Steps

**1. Set up the iMessage channel.** Follow OpenClaw's
[iMessage setup](https://docs.openclaw.ai/channels/imessage/setup):

```bash
brew install steipete/tap/imsg
openclaw plugins install @openclaw/imessage
openclaw channels status --probe --channel imessage
```

For effects, polls and unsend, enable [Private API mode](https://docs.openclaw.ai/channels/imessage/private-api)
(`imsg launch`, which needs SIP off; read its warning and ours before you do).

**2. Install the skill** into the agent's workspace (`~/.openclaw/workspace` unless you changed it). Run
this from that folder:

```bash
git clone --depth 1 https://github.com/abhaymettu/bubblewise
openclaw skills install ./bubblewise/skills/bubblewise
```

Add `--global` to share it with every agent on that state directory. `openclaw skills install
git:owner/repo` does not work for this repo, because the skill is not at the repository root. The clone
can be deleted afterwards; the install copies the skill.

**3. Tell the agent how the skill's markers map to OpenClaw.** The skill writes effects as `[[effect:NAME]]`
and sends with `bubblewise`. On OpenClaw, the skill's own rule is to use the platform's actions instead.
Add this to `AGENTS.md` in the workspace, which OpenClaw loads at the start of every session:

```markdown
## iMessage
Follow the bubblewise skill for when to style, add an effect, poll or unsend. Send with the message tool,
never the bubblewise CLI:
- **bold**, *italic*, ~~strike~~ in a normal reply become real styles.
- An effect: action sendWithEffect with effect set to the skill's name for it. The names match, except
  balloons is "balloon".
- A poll: action poll with pollQuestion, and pollOption repeated once per choice (2 to 12).
- Unsend: action unsend with the messageId of a message the gateway sent, within two minutes.
After a message-tool send to the chat you are answering, reply NO_REPLY so it is not sent twice.
```

## First test

1. `openclaw skills info bubblewise` shows the skill as found.
2. From your phone, text the agent: *Send me a confetti text that says the setup works.* One bubble arrives
   with confetti, and no second copy.
3. Text: *Make a poll: Thai, pizza or tacos?* A native poll arrives on iOS 26 and newer.

## Sources

From OpenClaw's docs and source (main, 2026-11-24): `docs/channels/imessage-from-bluebubbles.md`
(BlueBubbles removed), `docs/channels/imessage/rich-messages.md` and `private-api.md` (actions and their
parameters), `extensions/imessage/src/markdown-format.ts` (markdown to styles), `docs/cli/skills.md`
(`skills install`, `--global`, root `SKILL.md` for `git:`), `docs/tools/skills.md` (where skills load),
`docs/concepts/messages.md` (`NO_REPLY`) and `docs/automation/cron-jobs/delivery.md` (announce delivery).
