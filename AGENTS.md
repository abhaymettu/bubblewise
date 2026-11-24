# AGENTS.md

## What this is

`bubblewise` turns text an agent writes (markdown plus `[[effect:NAME]]`) into native iMessage sends
through imsg or a BlueBubbles server. `skill/SKILL.md` is the agent-facing guide; keep it in step with
the CLI.

## Layout

- `src/bubblewise/markup.py`: text to bubbles, UTF-16 style ranges and the effect. Pure, no I/O.
- `src/bubblewise/backends.py`: `Imsg` (subprocess) and `BlueBubbles` (urllib). Raise `Unsupported` when a
  backend cannot do something at all, `SendFailed` when it tried; `retry_safe` is true only when the
  request was refused before anything was sent.
- `src/bubblewise/cli.py`: `preview`, `send`, `poll`, `unsend`, `later`.
- `skill/SKILL.md`: when to use each feature. Written for the agent, not for developers.

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
  wording in `skill/SKILL.md` in the same change.
