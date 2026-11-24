import unittest

from bubblewise.markup import EFFECTS, parse, take_effect, utf16_len


def ranges(text, **kw):
    return [b.ranges for b in parse(text, **kw).bubbles]


class StylesTest(unittest.TestCase):
    def test_bold_and_italic_become_ranges_over_plain_text(self):
        message = parse("**Heads up**: the deploy is at *6pm*")
        self.assertEqual(message.plain, "Heads up: the deploy is at 6pm")
        self.assertEqual(
            ranges("**Heads up**: the deploy is at *6pm*"),
            [[{"start": 0, "length": 8, "styles": ["bold"]}, {"start": 27, "length": 3, "styles": ["italic"]}]],
        )

    def test_offsets_are_utf16_units(self):
        message = parse("café 👋 **now**")
        self.assertEqual(utf16_len("café 👋 "), 8)
        self.assertEqual(message.bubbles[0].ranges, [{"start": 8, "length": 3, "styles": ["bold"]}])

    def test_underline_and_strikethrough(self):
        self.assertEqual(
            parse("a <u>key</u> ~~old~~ new").bubbles[0].ranges,
            [
                {"start": 2, "length": 3, "styles": ["underline"]},
                {"start": 6, "length": 3, "styles": ["strikethrough"]},
            ],
        )

    def test_nested_styles_share_one_range(self):
        self.assertEqual(ranges("***both*** here"), [[{"start": 0, "length": 4, "styles": ["bold", "italic"]}]])

    def test_identifiers_and_arithmetic_stay_plain(self):
        message = parse("set MAX_RETRY_COUNT in config_file.json, 2*3*4")
        self.assertEqual(message.plain, "set MAX_RETRY_COUNT in config_file.json, 2*3*4")
        self.assertFalse(message.styled)

    def test_markdown_that_does_not_render_is_stripped(self):
        message = parse("## Plan\nRun `make test` then read [the docs](https://example.com)\n- one\n- two")
        self.assertEqual(message.plain, "Plan\nRun make test then read the docs\nhttps://example.com\n• one\n• two")

    def test_code_fences_are_removed_and_the_code_kept(self):
        self.assertEqual(parse("```bash\nls -la\n```").plain, "ls -la")

    def test_private_use_characters_in_input_are_dropped(self):
        self.assertEqual(parse("abc").plain, "abc")


class BubblesTest(unittest.TestCase):
    def test_each_paragraph_is_a_bubble_with_its_own_offsets(self):
        message = parse("First *one*\n\nthen **two**")
        self.assertEqual([b.text for b in message.bubbles], ["First one", "then two"])
        self.assertEqual(message.bubbles[1].ranges, [{"start": 5, "length": 3, "styles": ["bold"]}])

    def test_a_span_across_bubbles_stays_styled_in_both(self):
        message = parse("**one\n\ntwo**")
        self.assertEqual(
            [b.ranges for b in message.bubbles],
            [[{"start": 0, "length": 3, "styles": ["bold"]}], [{"start": 0, "length": 3, "styles": ["bold"]}]],
        )

    def test_one_bubble_when_asked(self):
        self.assertEqual(len(parse("a\n\nb", split_paragraphs=False).bubbles), 1)


class EffectsTest(unittest.TestCase):
    def test_marker_is_removed_and_named(self):
        message = parse("Happy birthday! [[effect:balloons]]")
        self.assertEqual((message.plain, message.effect_name), ("Happy birthday!", "balloons"))
        self.assertEqual(message.effect, EFFECTS["balloons"])

    def test_names_ignore_case_spaces_and_underscores(self):
        self.assertEqual(take_effect("[[Effect: Invisible Ink]] 42")[1], "invisibleink")
        self.assertEqual(take_effect("wow [[effect:shooting_star]]")[1], "shootingstar")

    def test_unknown_names_are_removed_without_an_effect(self):
        self.assertEqual(take_effect("[[effect:glitter]] hi"), ("hi", None))

    def test_marker_in_the_middle_leaves_one_space(self):
        self.assertEqual(parse("big news [[effect:slam]] we shipped").plain, "big news we shipped")

    def test_text_effects_are_opt_in(self):
        self.assertEqual(parse("that went [bloom]well[/bloom]").bubbles[0].ranges, [])
        self.assertEqual(
            parse("that went [bloom]well[/bloom]", text_effects=True).bubbles[0].ranges,
            [{"start": 10, "length": 4, "styles": ["bloom"]}],
        )
        self.assertEqual(parse("that went [bloom]well[/bloom]").plain, "that went well")


if __name__ == "__main__":
    unittest.main()
