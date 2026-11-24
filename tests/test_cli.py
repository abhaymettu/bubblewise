import contextlib
import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from bubblewise import cli
from bubblewise.backends import Unsupported

NOW = datetime(2030, 1, 2, 10, 0, tzinfo=timezone.utc)


class WhenTest(unittest.TestCase):
    def test_relative(self):
        self.assertEqual(cli.parse_when("+30m", NOW), NOW + timedelta(minutes=30))
        self.assertEqual(cli.parse_when("+2h", NOW), NOW + timedelta(hours=2))

    def test_clock_time_rolls_to_tomorrow_once_passed(self):
        self.assertEqual(cli.parse_when("18:45", NOW), NOW.replace(hour=18, minute=45))
        self.assertEqual(cli.parse_when("09:00", NOW), NOW.replace(hour=9) + timedelta(days=1))

    def test_iso(self):
        self.assertEqual(cli.parse_when("2030-01-03T09:00:00+00:00", NOW), NOW.replace(day=3, hour=9))


def run(argv, backend=None):
    out, err = io.StringIO(), io.StringIO()
    with (
        contextlib.redirect_stdout(out),
        contextlib.redirect_stderr(err),
        mock.patch.object(cli, "_backend", return_value=backend),
    ):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


class CommandsTest(unittest.TestCase):
    def test_preview_sends_nothing(self):
        code, out, _ = run(["preview", "**hi** [[effect:heart]]"])
        self.assertEqual(code, 0)
        self.assertEqual(
            json.loads(out),
            {"effect": "heart", "bubbles": [{"text": "hi", "ranges": [{"start": 0, "length": 2, "styles": ["bold"]}]}]},
        )

    def test_send(self):
        backend = mock.Mock()
        backend.send.return_value = ["G1"]
        code, out, _ = run(["send", "--chat", "C", "--json", "hello"], backend)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"sent": 1, "guids": ["G1"], "effect": None, "plain": False})

    def test_poll_falls_back_to_a_numbered_list(self):
        backend = mock.Mock()
        backend.poll.side_effect = Unsupported("no polls here")
        backend.send.return_value = ["G2"]
        code, _, err = run(["poll", "--chat", "C", "Dinner?", "Pizza", "Sushi"], backend)
        self.assertEqual(code, 0)
        self.assertIn("numbered list", err)
        sent = backend.send.call_args.args[1]
        self.assertEqual(sent.plain, "Dinner?\n\n1. Pizza\n2. Sushi")

    def test_poll_needs_two_options(self):
        with self.assertRaises(SystemExit):
            run(["poll", "--chat", "C", "Dinner?", "Pizza"], mock.Mock())

    def test_later_refuses_the_past(self):
        with self.assertRaises(SystemExit):
            run(["later", "--chat", "C", "--at", "2000-01-01T00:00:00+00:00", "hi"], mock.Mock())

    def test_allowlist_refuses_other_chats_before_any_backend_call(self):
        backend = mock.Mock()
        with mock.patch.dict("os.environ", {"BUBBLEWISE_ALLOWED_CHATS": "A, B"}):
            for argv in (
                ["send", "--chat", "C", "hi"],
                ["unsend", "--chat", "C", "G1"],
                ["poll", "--chat", "C", "Q?", "x", "y"],
                ["later", "--chat", "C", "--at", "+1h", "hi"],
            ):
                with self.assertRaises(SystemExit):
                    run(argv, backend)
            backend.send.return_value = ["G1"]
            self.assertEqual(run(["send", "--chat", "B", "hi"], backend)[0], 0)
        self.assertEqual(backend.send.call_count, 1)
        backend.unsend.assert_not_called()
        backend.poll.assert_not_called()

    def test_send_reports_no_effect_when_the_server_took_it_plain(self):
        backend = mock.Mock(sent_plain=True)
        backend.send.return_value = ["G1"]
        code, out, _ = run(["send", "--json", "--chat", "C", "We did it [[effect:confetti]]"], backend)
        self.assertEqual(json.loads(out), {"sent": 1, "guids": ["G1"], "effect": None, "plain": True})

    def test_chats_shows_only_allowed_chats_once_the_list_is_set(self):
        backend = mock.Mock()
        backend.chats.return_value = [
            {"guid": "A", "name": "Sam", "participants": []},
            {"guid": "B", "name": "Trip", "participants": []},
        ]
        with mock.patch.dict("os.environ", {"BUBBLEWISE_ALLOWED_CHATS": "B"}):
            code, out, _ = run(["chats", "--json"], backend)
        self.assertEqual([c["guid"] for c in json.loads(out)], ["B"])

    def test_backend_errors_exit_one_with_the_reason(self):
        backend = mock.Mock()
        backend.unsend.side_effect = Unsupported("too late")
        code, _, err = run(["unsend", "--chat", "C", "G1"], backend)
        self.assertEqual((code, err.strip()), (1, "bubblewise: too late"))


class BackendChoiceTest(unittest.TestCase):
    def choose(self, env):
        with mock.patch.dict("os.environ", env, clear=True):
            return cli._backend(cli.build_parser().parse_args(["send", "--chat", "C", "hi"]))

    def test_own_password_name_wins_for_gateways_that_hide_the_shared_one(self):
        backend = self.choose(
            {
                "BLUEBUBBLES_URL": "http://bb.example.com:1234/",
                "BLUEBUBBLES_PASSWORD": "shared",
                "BUBBLEWISE_BLUEBUBBLES_PASSWORD": "own",
            }
        )
        self.assertEqual(
            (backend.name, backend.url, backend.password), ("bluebubbles", "http://bb.example.com:1234", "own")
        )

    def test_shared_password_name_still_works(self):
        backend = self.choose({"BLUEBUBBLES_URL": "http://bb.example.com", "BLUEBUBBLES_PASSWORD": "shared"})
        self.assertEqual(backend.password, "shared")

    def test_missing_password_names_both_variables(self):
        with self.assertRaises(SystemExit) as caught:
            self.choose({"BUBBLEWISE_BACKEND": "bluebubbles", "BLUEBUBBLES_URL": "http://bb.example.com"})
        self.assertIn("BUBBLEWISE_BLUEBUBBLES_PASSWORD", str(caught.exception))

    def test_imsg_is_the_default(self):
        self.assertEqual(self.choose({}).name, "imsg")


if __name__ == "__main__":
    unittest.main()
