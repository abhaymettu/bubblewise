# AGENTS.md

## Start here if you are wiring bubblewise into an agent

Open the recipe for the agent you are setting up and follow it as written; the steps differ by agent.

| Agent | Recipe | In one line |
|---|---|---|
| Hermes Agent | [docs/recipes/hermes.md](docs/recipes/hermes.md) | BlueBubbles, CLI plus skill, `BUBBLEWISE_BLUEBUBBLES_PASSWORD`, `allow_silence: true` |
| OpenClaw | [docs/recipes/openclaw.md](docs/recipes/openclaw.md) | Skill only; OpenClaw's iMessage plugin already sends styles, effects, polls and unsend |
| Claude Code, Codex, anything with a shell | [docs/recipes/any-agent.md](docs/recipes/any-agent.md) | CLI plus skill, imsg on the same Mac |

- Skill: `skills/bubblewise/SKILL.md`. CLI: `pipx install git+https://github.com/abhaymettu/bubblewise`.
- Check before you send: `bubblewise preview "<text>"` sends nothing.
- Never send a test text to anyone but the owner, and set `BUBBLEWISE_ALLOWED_CHATS`.
- Read [docs/security.md](docs/security.md) before giving an agent the bridge.

The rest of this file is for working on the bubblewise code.

## What this is

`bubblewise` turns text an agent writes (markdown plus `[[effect:NAME]]`) into native iMessage sends
through imsg or a BlueBubbles server. `skills/bubblewise/SKILL.md` is the agent-facing guide; keep it in
step with the CLI. `docs/recipes/` says how each agent wires it in; keep each recipe's "What works today"
table in step with README.md.

## Layout

- `src/bubblewise/markup.py`: text to bubbles, UTF-16 style ranges and the effect. Pure, no I/O.
- `src/bubblewise/backends.py`: `Imsg` (subprocess) and `BlueBubbles` (urllib). Raise `Unsupported` when a
  backend cannot do something at all, `SendFailed` when it tried; `retry_safe` is true only when the
  request was refused before anything was sent.
- `src/bubblewise/cli.py`: `preview`, `send`, `poll`, `unsend`, `later`, `chats`. `chats` lists only allowed
  chats once `BUBBLEWISE_ALLOWED_CHATS` is set.
- `skills/bubblewise/SKILL.md`: when to use each feature. Written for the agent, not for developers.

- `docs/recipes/`: one page per agent (Hermes, OpenClaw, any agent with a shell). Every config key in them
  comes from that agent's own docs or source, named at the end of the page.
- `llms.txt`: the index an agent reads first. Update it when a page is added or moved.
- `docs/self-hosting.md`, `docs/security.md`: setting up imsg or BlueBubbles for an agent, and running it
  safely. General guidance only; never add anything from one person's setup.

## Run and test

```bash
PYTHONPATH=src python -m unittest discover -s tests
PYTHONPATH=src python -m bubblewise preview "**hi** [[effect:heart]]"
```

Python 3.10+, standard library only. Do not add dependencies.

## Rules

- Tests never send a real message. Backends take an injected `run` or `opener`; use the fakes in
  `tests/test_backends.py`.
- Fixtures use reserved numbers (`+1555555xxxx`) and `example.com` only.
- A send that may have reached Messages is never retried automatically. Only a 4xx refusal of styled text
  falls back to plain text.
- Offsets are UTF-16 code units. Any change to `markup.py` needs a test with an emoji before the range.
- `BUBBLEWISE_ALLOWED_CHATS` is checked in `cli.main` before any backend call. Keep it that way for every
  new command that takes `--chat`.
- When a feature's support changes upstream (imsg or BlueBubbles), update the table in README.md and the
  wording in `skills/bubblewise/SKILL.md` in the same change.
