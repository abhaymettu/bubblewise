"""Turn what an agent writes into what iMessage can show natively.

An agent writes ordinary markdown plus two small markers. This module turns that into bubbles: the
plain text of each, the style ranges Messages understands (UTF-16 offsets, the way Messages and
BlueBubbles count), and the one send effect, if any.

    **bold**  *italic*  ~~strikethrough~~  <u>underline</u>
    [bloom]animated words[/bloom]            one text effect per span (opt-in, see TEXT_EFFECTS)
    [[effect:confetti]]                      a bubble or screen effect for the whole message
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STYLES = ("bold", "italic", "underline", "strikethrough")

# Bubble and screen effects, by the names people use, with the identifiers Messages sends.
EFFECTS = {
    "slam": "com.apple.MobileSMS.expressivesend.impact",
    "loud": "com.apple.MobileSMS.expressivesend.loud",
    "gentle": "com.apple.MobileSMS.expressivesend.gentle",
    "invisibleink": "com.apple.MobileSMS.expressivesend.invisibleink",
    "confetti": "com.apple.messages.effect.CKConfettiEffect",
    "balloons": "com.apple.messages.effect.CKHappyBirthdayEffect",
    "fireworks": "com.apple.messages.effect.CKFireworksEffect",
    "heart": "com.apple.messages.effect.CKHeartEffect",
    "lasers": "com.apple.messages.effect.CKLasersEffect",
    "sparkles": "com.apple.messages.effect.CKSparklesEffect",
    "spotlight": "com.apple.messages.effect.CKSpotlightEffect",
    "echo": "com.apple.messages.effect.CKEchoEffect",
    "shootingstar": "com.apple.messages.effect.CKShootingStarEffect",
}

# Animated text effects from the Messages picker (macOS 15 / iOS 18). Only some senders can set them.
TEXT_EFFECTS = ("big", "small", "shake", "nod", "explode", "ripple", "bloom", "jitter")

_OPEN = {name: chr(0xE000 + 2 * i) for i, name in enumerate(STYLES + TEXT_EFFECTS)}
_CLOSE = {name: chr(0xE001 + 2 * i) for i, name in enumerate(STYLES + TEXT_EFFECTS)}
_MARK = {**{c: (n, True) for n, c in _OPEN.items()}, **{c: (n, False) for n, c in _CLOSE.items()}}
_MARK_RE = re.compile("[-]")

_EFFECT_RE = re.compile(r"[ \t]*\[\[effect:\s*([A-Za-z_ -]+?)\s*\]\][ \t]*", re.IGNORECASE)
_SPAN_RULES = (
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.DOTALL), "bold"),
    (re.compile(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", re.DOTALL), "italic"),
    (re.compile(r"\b__(?![\s_])(.+?)(?<![\s_])__\b", re.DOTALL), "bold"),
    (re.compile(r"\b_(?![\s_])(.+?)(?<![\s_])_\b", re.DOTALL), "italic"),
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.DOTALL), "strikethrough"),
    (re.compile(r"<u>(.+?)</u>", re.DOTALL | re.IGNORECASE), "underline"),
)
_TEXT_EFFECT_RE = re.compile(r"\[(" + "|".join(TEXT_EFFECTS) + r")\](.+?)\[/\1\]", re.DOTALL | re.IGNORECASE)
_BLOCK_RULES = (
    (re.compile(r"^```[\w+-]*[ \t]*\n?|\n?^```[ \t]*$", re.MULTILINE), ""),
    (re.compile(r"`([^`\n]+)`"), r"\1"),
    (re.compile(r"^#{1,6}[ \t]+", re.MULTILINE), ""),
    (re.compile(r"^[ \t]*[-*+][ \t]+", re.MULTILINE), "• "),
    (
        re.compile(r"!?\[([^\]]+)\]\((https?://[^)\s]+)\)"),
        lambda m: m.group(2) if m.group(1) == m.group(2) else f"{m.group(1)}\n{m.group(2)}",
    ),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r"\1"),
)


@dataclass
class Bubble:
    text: str
    ranges: list[dict] = field(default_factory=list)


@dataclass
class Message:
    bubbles: list[Bubble]
    effect: str | None = None
    effect_name: str | None = None

    @property
    def styled(self) -> bool:
        return any(b.ranges for b in self.bubbles)

    @property
    def plain(self) -> str:
        return "\n\n".join(b.text for b in self.bubbles)


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def take_effect(text: str) -> tuple[str, str | None]:
    """Remove every [[effect:NAME]] marker; return the text and the first known effect's name."""
    names: list[str] = []

    def _take(match: re.Match[str]) -> str:
        names.append(re.sub(r"[\s_-]", "", match.group(1).lower()))
        return " " if match.start() and match.end() < len(match.string) else ""

    cleaned = _EFFECT_RE.sub(_take, text)
    return cleaned, next((n for n in names if n in EFFECTS), None)


def _mark_spans(text: str, text_effects: bool) -> str:
    text = _MARK_RE.sub("", text)
    text = _TEXT_EFFECT_RE.sub(
        lambda m: (
            f"{_OPEN[m.group(1).lower()]}{m.group(2)}{_CLOSE[m.group(1).lower()]}" if text_effects else m.group(2)
        ),
        text,
    )
    for pattern, style in _SPAN_RULES:
        text = pattern.sub(lambda m, s=style: f"{_OPEN[s]}{m.group(1)}{_CLOSE[s]}", text)
    for pattern, repl in _BLOCK_RULES:
        text = pattern.sub(repl, text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _bubble(marked: str, active: frozenset[str]) -> tuple[Bubble, frozenset[str]]:
    """One bubble's marked text -> its plain text and ranges; styles still open carry to the next."""
    open_now = set(active)
    plain, ranges, offset = [], [], 0
    for piece in re.split(r"([-])", marked):
        if piece in _MARK:
            name, opening = _MARK[piece]
            (open_now.add if opening else open_now.discard)(name)
            continue
        if not piece:
            continue
        size = utf16_len(piece)
        styles = [s for s in STYLES + TEXT_EFFECTS if s in open_now]
        if styles and piece.strip():
            last = ranges[-1] if ranges else None
            if last and last["styles"] == styles and last["start"] + last["length"] == offset:
                last["length"] += size
            else:
                ranges.append({"start": offset, "length": size, "styles": styles})
        plain.append(piece)
        offset += size
    text = "".join(plain)
    lead, body = utf16_len(text) - utf16_len(text.lstrip()), text.strip()
    end, kept = utf16_len(body), []
    for r in ranges:
        start, stop = max(r["start"] - lead, 0), min(r["start"] + r["length"] - lead, end)
        if stop > start:
            kept.append({"start": start, "length": stop - start, "styles": r["styles"]})
    return Bubble(body, kept), frozenset(open_now)


def parse(text: str, *, text_effects: bool = False, split_paragraphs: bool = True) -> Message:
    """Agent text -> Message. With ``split_paragraphs`` each paragraph becomes its own bubble, the way
    people text. ``text_effects`` keeps [bloom]...[/bloom] spans as ranges; otherwise only the words stay."""
    body, effect_name = take_effect(text or "")
    marked = _mark_spans(body, text_effects)
    parts = re.split(r"\n[ \t]*\n", marked) if split_paragraphs else [marked]
    bubbles, active = [], frozenset()
    for part in parts:
        bubble, active = _bubble(part, active)
        if bubble.text:
            bubbles.append(bubble)
    return Message(bubbles, EFFECTS.get(effect_name) if effect_name else None, effect_name)
