"""Two ways to reach Messages on a Mac: the imsg CLI, or a BlueBubbles server's REST API.

Both take the same parsed Message and say plainly when they cannot do something, so the caller can
fall back (a poll becomes a numbered list) instead of failing silently.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from typing import Callable

from .markup import Message


class Unsupported(Exception):
    """This backend cannot do this at all; the caller should fall back."""


class SendFailed(Exception):
    """The backend tried and failed; ``retry_safe`` says whether sending again could duplicate."""

    def __init__(self, message: str, *, retry_safe: bool = False):
        super().__init__(message)
        self.retry_safe = retry_safe


class Imsg:
    """github.com/steipete/imsg. Styles, effects, polls and unsend use its injected helper."""

    name = "imsg"

    def __init__(self, binary: str = "imsg", run: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.binary, self._run = binary, run

    def _call(self, *args: str) -> dict:
        proc = self._run([self.binary, *args, "--json"], capture_output=True, text=True, timeout=180)
        if proc.returncode != 0:
            raise SendFailed(f"imsg {args[0]}: {(proc.stderr or proc.stdout).strip()[:300]}")
        out = (proc.stdout or "").strip().splitlines()
        try:
            return json.loads(out[-1]) if out else {}
        except ValueError:
            return {"raw": out[-1]}

    @staticmethod
    def _guid(data: dict) -> str:
        return str(data.get("messageGuid") or data.get("guid") or data.get("message_guid") or "")

    def send(self, chat: str, message: Message, *, reply_to: str | None = None) -> list[str]:
        guids = []
        for index, bubble in enumerate(message.bubbles):
            args = ["send-rich", "--chat", chat, "--text", bubble.text]
            if bubble.ranges:
                args += ["--format", json.dumps(bubble.ranges, separators=(",", ":"))]
            if index == 0 and message.effect:
                args += ["--effect", message.effect]
            if reply_to:
                args += ["--reply-to", reply_to]
            guids.append(self._guid(self._call(*args)))
        return guids

    def poll(self, chat: str, question: str, options: list[str]) -> str:
        args = ["poll", "send", "--chat", chat, "--question", question]
        for option in options:
            args += ["--option", option]
        return self._guid(self._call(*args))

    def unsend(self, chat: str, guid: str) -> None:
        self._call("unsend", "--chat", chat, "--message", guid)

    def send_later(self, chat: str, message: Message, at: datetime) -> list[str]:
        if message.effect:
            raise Unsupported("Send Later carries text and styles only, not effects")
        guids = []
        for bubble in message.bubbles:
            args = ["send-rich", "--chat", chat, "--text", bubble.text, "--send-at", at.isoformat()]
            if bubble.ranges:
                args += ["--format", json.dumps(bubble.ranges, separators=(",", ":"))]
            guids.append(self._guid(self._call(*args)))
        return guids


Opener = Callable[[urllib.request.Request, float], object]


class BlueBubbles:
    """A BlueBubbles server (bluebubbles.app). Styles, effects and unsend need its Private API helper."""

    name = "bluebubbles"

    def __init__(self, url: str, password: str, opener: Opener | None = None):
        self.url, self.password = url.rstrip("/"), password
        self._open = opener or (lambda request, timeout: urllib.request.urlopen(request, timeout=timeout))

    def _post(self, path: str, body: dict) -> dict:
        query = urllib.parse.urlencode({"password": self.password})
        request = urllib.request.Request(
            f"{self.url}/api/v1/{path}?{query}",
            data=json.dumps(body).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with self._open(request, 60) as response:
                return json.loads(response.read() or b"{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:300]
            exc.close()
            raise SendFailed(f"BlueBubbles {path}: HTTP {exc.code} {detail}", retry_safe=400 <= exc.code < 500) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise SendFailed(f"BlueBubbles {path}: {getattr(exc, 'reason', exc)}") from exc

    @staticmethod
    def _guid(data: dict) -> str:
        inner = data.get("data") if isinstance(data.get("data"), dict) else {}
        return str(inner.get("guid") or inner.get("messageGuid") or "")

    def send(self, chat: str, message: Message, *, reply_to: str | None = None) -> list[str]:
        guids = []
        for index, bubble in enumerate(message.bubbles):
            body: dict = {"chatGuid": chat, "tempGuid": f"temp-{uuid.uuid4()}", "message": bubble.text}
            rich: dict = {}
            if bubble.ranges:
                rich["textFormatting"] = bubble.ranges
            if index == 0 and message.effect:
                rich["effectId"] = message.effect
            if reply_to:
                rich.update(selectedMessageGuid=reply_to, partIndex=0)
            if rich:
                body.update(method="private-api", **rich)
            try:
                guids.append(self._guid(self._post("message/text", body)))
            except SendFailed as exc:
                if message.effect_name == "invisibleink" and index == 0:
                    raise SendFailed(f"{exc}; invisible ink not sent as plain text") from exc
                if not (exc.retry_safe and (bubble.ranges or (index == 0 and message.effect))):
                    raise
                plain = {"chatGuid": chat, "tempGuid": f"temp-{uuid.uuid4()}", "message": bubble.text}
                guids.append(self._guid(self._post("message/text", plain)))
        return guids

    def poll(self, chat: str, question: str, options: list[str]) -> str:
        raise Unsupported("BlueBubbles has no route for creating polls yet")

    def unsend(self, chat: str, guid: str) -> None:
        self._post(f"message/{urllib.parse.quote(guid, safe='')}/unsend", {"partIndex": 0})

    def send_later(self, chat: str, message: Message, at: datetime) -> list[str]:
        """The server's own scheduler: plain text only, and the server must be running at that time."""
        when = int(at.timestamp() * 1000)
        for bubble in message.bubbles:
            self._post(
                "message/schedule",
                {
                    "type": "send-message",
                    "scheduledFor": when,
                    "schedule": {"type": "once"},
                    "payload": {"chatGuid": chat, "message": bubble.text, "method": "apple-script"},
                },
            )
        return []
