"""bubblewise: send what an agent writes as native iMessage bubbles, polls and Send Later texts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

from . import __version__
from .backends import BlueBubbles, Imsg, SendFailed, Unsupported
from .markup import parse


def _backend(args):
    kind = (
        args.backend
        or os.environ.get("BUBBLEWISE_BACKEND")
        or ("bluebubbles" if os.environ.get("BLUEBUBBLES_URL") else "imsg")
    )
    if kind == "bluebubbles":
        url, password = os.environ.get("BLUEBUBBLES_URL"), os.environ.get("BLUEBUBBLES_PASSWORD")
        if not url or not password:
            raise SystemExit("bubblewise: set BLUEBUBBLES_URL and BLUEBUBBLES_PASSWORD")
        return BlueBubbles(url, password)
    return Imsg(os.environ.get("IMSG_BIN", "imsg"))


def check_allowed(chat: str) -> None:
    """Refuse a chat that is not on BUBBLEWISE_ALLOWED_CHATS, when that list is set."""
    allowed = {c.strip() for c in os.environ.get("BUBBLEWISE_ALLOWED_CHATS", "").split(",") if c.strip()}
    if allowed and chat not in allowed:
        raise SystemExit(f"bubblewise: {chat} is not in BUBBLEWISE_ALLOWED_CHATS; nothing sent")


def _text(args) -> str:
    text = " ".join(args.text) if args.text else sys.stdin.read()
    if not text.strip():
        raise SystemExit("bubblewise: nothing to send")
    return text


def parse_when(raw: str, now: datetime | None = None) -> datetime:
    """'+30m', '+2h', '+1d', '18:45' (next time it is 18:45) or an ISO 8601 time, as a local datetime."""
    now = now or datetime.now().astimezone()
    if match := re.fullmatch(r"\+(\d+)([mhd])", raw.strip()):
        unit = {"m": "minutes", "h": "hours", "d": "days"}[match.group(2)]
        return now + timedelta(**{unit: int(match.group(1))})
    if match := re.fullmatch(r"(\d{1,2}):(\d{2})", raw.strip()):
        at = now.replace(hour=int(match.group(1)), minute=int(match.group(2)), second=0, microsecond=0)
        return at if at > now else at + timedelta(days=1)
    at = datetime.fromisoformat(raw.strip())
    return at if at.tzinfo else at.astimezone()


def _emit(args, payload: dict) -> None:
    if args.json:
        print(json.dumps(payload))
    else:
        print(" ".join(f"{k}={v}" for k, v in payload.items() if v not in (None, "", [])))


def cmd_preview(args) -> int:
    message = parse(_text(args), text_effects=args.text_effects)
    print(
        json.dumps(
            {"effect": message.effect_name, "bubbles": [{"text": b.text, "ranges": b.ranges} for b in message.bubbles]},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_send(args) -> int:
    message = parse(_text(args), text_effects=args.text_effects)
    guids = _backend(args).send(args.chat, message, reply_to=args.reply_to)
    _emit(args, {"sent": len(guids), "guids": guids, "effect": message.effect_name})
    return 0


def cmd_poll(args) -> int:
    if len(args.options) < 2:
        raise SystemExit("bubblewise: a poll needs at least two options")
    backend = _backend(args)
    try:
        guid = backend.poll(args.chat, args.question, args.options)
        _emit(args, {"poll": guid})
    except Unsupported as why:
        lines = [args.question, ""] + [f"{i}. {o}" for i, o in enumerate(args.options, 1)]
        guids = backend.send(args.chat, parse("\n".join(lines), split_paragraphs=False))
        print(f"bubblewise: {why}; sent a numbered list instead", file=sys.stderr)
        _emit(args, {"poll": None, "fallback": "list", "guids": guids})
    return 0


def cmd_unsend(args) -> int:
    _backend(args).unsend(args.chat, args.guid)
    _emit(args, {"unsent": args.guid})
    return 0


def cmd_later(args) -> int:
    at = parse_when(args.at)
    if at <= datetime.now().astimezone():
        raise SystemExit("bubblewise: that time has already passed")
    message = parse(_text(args))
    backend = _backend(args)
    if isinstance(backend, BlueBubbles) and (message.styled or message.effect):
        print("bubblewise: BlueBubbles schedules plain text; styles and effects are dropped", file=sys.stderr)
    guids = backend.send_later(args.chat, message, at)
    _emit(args, {"scheduled": at.isoformat(timespec="minutes"), "guids": guids})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bubblewise", description=__doc__)
    parser.add_argument("--version", action="version", version=f"bubblewise {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_text, *, chat=True, text=True):
        p = sub.add_parser(name, help=help_text)
        p.set_defaults(func=func)
        p.add_argument("--backend", choices=("imsg", "bluebubbles"))
        p.add_argument("--json", action="store_true", help="print one JSON object")
        if chat:
            p.add_argument("--chat", required=True, help="chat GUID, e.g. iMessage;-;+15551234567")
        if text:
            p.add_argument("text", nargs="*", help="the message (read from stdin when omitted)")
        return p

    p = add("preview", cmd_preview, "show the bubbles, ranges and effect without sending", chat=False)
    p.add_argument("--text-effects", action="store_true", help="keep [bloom]...[/bloom] spans")
    p = add("send", cmd_send, "send text with native styles and an optional effect")
    p.add_argument("--reply-to", help="thread the reply under this message GUID")
    p.add_argument("--text-effects", action="store_true", help="send [bloom]...[/bloom] spans (imsg only)")
    p = add("poll", cmd_poll, "send a native poll (a numbered list where polls are not available)", text=False)
    p.add_argument("question")
    p.add_argument("options", nargs="+")
    p = add("unsend", cmd_unsend, "unsend one of your messages (within two minutes)", text=False)
    p.add_argument("guid")
    p = add("later", cmd_later, "schedule a text: +30m, +2h, 18:45 or an ISO time")
    p.add_argument("--at", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "chat", None):
        check_allowed(args.chat)
    try:
        return args.func(args)
    except (SendFailed, Unsupported) as exc:
        print(f"bubblewise: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
