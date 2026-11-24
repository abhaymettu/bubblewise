import io
import json
import subprocess
import unittest
import urllib.error
from datetime import datetime, timezone

from bubblewise.backends import BlueBubbles, Imsg, SendFailed, Unsupported
from bubblewise.markup import EFFECTS, parse

CHAT = "iMessage;-;+15555550100"


class FakeRun:
    def __init__(self, stdout='{"messageGuid":"G1"}', returncode=0, stderr=""):
        self.calls, self.stdout, self.returncode, self.stderr = [], stdout, returncode, stderr

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeServer:
    def __init__(self, fail=None):
        self.requests, self.fail = [], fail or (lambda body: None)

    def __call__(self, request, timeout):
        body = json.loads(request.data)
        self.requests.append((request.full_url, body))
        if code := self.fail(body):
            raise urllib.error.HTTPError(request.full_url, code, "no", {}, io.BytesIO(b'{"error":"no"}'))
        return FakeResponse(json.dumps({"status": 200, "data": {"guid": f"G{len(self.requests)}"}}).encode())


class ImsgTest(unittest.TestCase):
    def test_styled_bubble_with_effect(self):
        run = FakeRun()
        guids = Imsg(run=run).send(CHAT, parse("Meet at **6** [[effect:slam]]\n\nsee you"))
        self.assertEqual(guids, ["G1", "G1"])
        self.assertEqual(
            run.calls[0],
            [
                "imsg",
                "send-rich",
                "--chat",
                CHAT,
                "--text",
                "Meet at 6",
                "--format",
                '[{"start":8,"length":1,"styles":["bold"]}]',
                "--effect",
                EFFECTS["slam"],
                "--json",
            ],
        )
        self.assertNotIn("--effect", run.calls[1])

    def test_poll(self):
        run = FakeRun()
        self.assertEqual(Imsg(run=run).poll(CHAT, "Dinner?", ["Pizza", "Sushi"]), "G1")
        self.assertEqual(
            run.calls[0][1:],
            [
                "poll",
                "send",
                "--chat",
                CHAT,
                "--question",
                "Dinner?",
                "--option",
                "Pizza",
                "--option",
                "Sushi",
                "--json",
            ],
        )

    def test_unsend(self):
        run = FakeRun()
        Imsg(run=run).unsend(CHAT, "G9")
        self.assertEqual(run.calls[0][1:], ["unsend", "--chat", CHAT, "--message", "G9", "--json"])

    def test_send_later_passes_an_iso_time(self):
        run = FakeRun()
        at = datetime(2030, 1, 2, 9, 0, tzinfo=timezone.utc)
        Imsg(run=run).send_later(CHAT, parse("*morning*"), at)
        self.assertIn("--send-at", run.calls[0])
        self.assertEqual(run.calls[0][run.calls[0].index("--send-at") + 1], "2030-01-02T09:00:00+00:00")

    def test_send_later_refuses_effects(self):
        with self.assertRaises(Unsupported):
            Imsg(run=FakeRun()).send_later(CHAT, parse("hi [[effect:heart]]"), datetime.now(timezone.utc))

    def test_chats_reads_one_json_object_per_line(self):
        lines = [
            {"guid": CHAT, "name": "", "contactName": "Sam", "participants": ["+15555550100"]},
            {"identifier": "chat0001", "displayName": "Trip", "participants": ["a@example.com", "b@example.com"]},
        ]
        run = FakeRun(stdout="\n".join(json.dumps(line) for line in lines) + "\n")
        chats = Imsg(run=run).chats(5)
        self.assertEqual(run.calls[0], ["imsg", "chats", "--limit", "5", "--json"])
        self.assertEqual(
            chats,
            [
                {"guid": CHAT, "name": "Sam", "participants": ["+15555550100"]},
                {"guid": "chat0001", "name": "Trip", "participants": ["a@example.com", "b@example.com"]},
            ],
        )

    def test_a_failure_says_what_imsg_said(self):
        with self.assertRaisesRegex(SendFailed, "helper not injected"):
            Imsg(run=FakeRun(returncode=1, stderr="helper not injected")).send(CHAT, parse("hi"))


class BlueBubblesTest(unittest.TestCase):
    def server(self, **kw):
        fake = FakeServer(**kw)
        return BlueBubbles("http://localhost:1234/", "pw", opener=fake), fake

    def test_styled_send_uses_the_private_api(self):
        bb, fake = self.server()
        self.assertEqual(bb.send(CHAT, parse("Meet at **6** [[effect:confetti]]")), ["G1"])
        url, body = fake.requests[0]
        self.assertTrue(url.startswith("http://localhost:1234/api/v1/message/text?password=pw"))
        self.assertEqual(body["message"], "Meet at 6")
        self.assertEqual(body["method"], "private-api")
        self.assertEqual(body["textFormatting"], [{"start": 8, "length": 1, "styles": ["bold"]}])
        self.assertEqual(body["effectId"], EFFECTS["confetti"])

    def test_plain_send_stays_on_the_default_path(self):
        bb, fake = self.server()
        bb.send(CHAT, parse("just words"))
        self.assertNotIn("method", fake.requests[0][1])

    def test_rejected_styles_are_sent_again_plain(self):
        bb, fake = self.server(fail=lambda body: 400 if "textFormatting" in body else None)
        self.assertEqual(bb.send(CHAT, parse("Meet at **6**")), ["G2"])
        self.assertNotIn("textFormatting", fake.requests[1][1])
        self.assertEqual(fake.requests[1][1]["message"], "Meet at 6")

    def test_a_rejected_effect_is_reported_as_plain(self):
        bb, fake = self.server(fail=lambda body: 400 if "effectId" in body else None)
        self.assertEqual(bb.send(CHAT, parse("We did it [[effect:confetti]]")), ["G2"])
        self.assertTrue(bb.sent_plain)
        bb.send(CHAT, parse("just words"))
        self.assertFalse(bb.sent_plain)

    def test_chats_lists_guids_names_and_people(self):
        def opener(request, timeout):
            self.assertIn("/api/v1/chat/query?", request.full_url)
            self.assertEqual(json.loads(request.data), {"limit": 3})
            chat = {
                "guid": CHAT,
                "chatIdentifier": "+15555550100",
                "displayName": "",
                "participants": [{"address": "+15555550100"}],
            }
            return FakeResponse(json.dumps({"status": 200, "data": [chat]}).encode())

        chats = BlueBubbles("http://localhost:1234", "pw", opener=opener).chats(3)
        self.assertEqual(chats, [{"guid": CHAT, "name": "+15555550100", "participants": ["+15555550100"]}])

    def test_rejected_invisible_ink_is_never_resent_plain(self):
        bb, fake = self.server(fail=lambda body: 400)
        with self.assertRaisesRegex(SendFailed, "invisible ink"):
            bb.send(CHAT, parse("[[effect:invisibleink]] the butler did it"))
        self.assertEqual(len(fake.requests), 1)

    def test_server_errors_are_never_sent_twice(self):
        bb, fake = self.server(fail=lambda body: 500)
        with self.assertRaises(SendFailed):
            bb.send(CHAT, parse("Meet at **6**"))
        self.assertEqual(len(fake.requests), 1)

    def test_polls_are_unsupported(self):
        bb, _ = self.server()
        with self.assertRaises(Unsupported):
            bb.poll(CHAT, "Dinner?", ["Pizza", "Sushi"])

    def test_unsend_route(self):
        bb, fake = self.server()
        bb.unsend(CHAT, "AB/C")
        self.assertIn("/api/v1/message/AB%2FC/unsend?", fake.requests[0][0])
        self.assertEqual(fake.requests[0][1], {"partIndex": 0})

    def test_send_later_uses_the_server_scheduler(self):
        bb, fake = self.server()
        at = datetime(2030, 1, 2, 9, 0, tzinfo=timezone.utc)
        bb.send_later(CHAT, parse("**morning**"), at)
        body = fake.requests[0][1]
        self.assertEqual(body["scheduledFor"], int(at.timestamp() * 1000))
        self.assertEqual(body["payload"], {"chatGuid": CHAT, "message": "morning", "method": "apple-script"})


if __name__ == "__main__":
    unittest.main()
