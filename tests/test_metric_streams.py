"""Owned fixtures with hand-specified instruments, independent of old code."""
import difflib
import itertools
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from covewm import metrics as m


# source, tokens, identifiers, normalized tokens, controls, syntax, style labels
ASSIGN = {"Module": 1, "Assign": 1, "Name": 1, "Store": 1, "Constant": 1}
FIXTURES = {
    "python": [
        ("", [], [], [], {}, {"Module": 1}, []),
        ("x = 1\n", ["x", "=", "1"], ["x"], ["<ID>", "=", "<NUM>"], {}, ASSIGN, ["lower"]),
        ("total = 2\n", ["total", "=", "2"], ["total"], ["<ID>", "=", "<NUM>"], {}, ASSIGN, ["lower"]),
        ("x = '#hidden'\n", ["x", "="], ["x"], ["<ID>", "="], {}, ASSIGN, ["lower"]),
        ("def f(: # return\n", ["def", "f", "(", ":"], ["f"], ["def", "<ID>", "(", ":"], {}, {"PARSE_FAILURE": 1}, ["lower"]),
        ("except catch raise throw", ["except", "catch", "raise", "throw"], ["catch", "throw"],
         ["except", "<ID>", "raise", "<ID>"], {"catch": 2, "throw": 2}, {"PARSE_FAILURE": 1}, ["lower", "lower"]),
        ("_foo HTTP snake_case lowerCamel UpperCamel miX_ED $_", ["_foo", "HTTP", "snake_case", "lowerCamel", "UpperCamel", "miX_ED", "$_"],
         ["_foo", "HTTP", "snake_case", "lowerCamel", "UpperCamel", "miX_ED", "$_"], ["<ID>"] * 7, {}, {"PARSE_FAILURE": 1},
         ["prefixed_lower", "upper", "snake", "lower_camel", "upper_camel", "mixed", "empty"]),
        ("é = 1\u2028x = 2", ["=", "1", "x", "=", "2"], ["x"], ["=", "<NUM>", "<ID>", "=", "<NUM>"], {}, {"PARSE_FAILURE": 1}, ["lower"]),
    ],
    "javascript": [
        ("", [], [], [], {}, {}, []),
        ("const x = 1;", ["const", "x", "=", "1", ";"], ["x"], ["const", "<ID>", "=", "<NUM>", ";"], {},
         {"VariableDeclaration": 1, "AssignmentExpression": 1, "Identifier": 1, "Literal": 1}, ["lower"]),
        ('const name = "//hidden"; return value;', ["const", "name", "="], ["name"], ["const", "<ID>", "="], {},
         {"VariableDeclaration": 1, "AssignmentExpression": 1, "Identifier": 1}, ["lower"]),
        ("catch except throw raise", ["catch", "except", "throw", "raise"], ["except", "raise"],
         ["catch", "<ID>", "throw", "<ID>"], {"catch": 2, "throw": 2}, {"ThrowStatement": 1, "Identifier": 2}, ["lower", "lower"]),
        ("foo(1) && a[2] !== 3;", ["foo", "(", "1", ")", "&&", "a", "[", "2", "]", "!==", "3", ";"], ["foo", "a"],
         ["<ID>", "(", "<NUM>", ")", "&&", "<ID>", "[", "<NUM>", "]", "!==", "<NUM>", ";"], {},
         {"CallExpression": 1, "MemberExpression": 1, "ArrayExpression": 1, "LogicalExpression": 1, "ComparisonExpression": 1, "Identifier": 2, "Literal": 3}, ["lower", "lower"]),
    ],
}


def overlap(left, right):
    keys = set(left) | set(right)
    union = sum(max(left.get(k, 0), right.get(k, 0)) for k in keys)
    return sum(min(left.get(k, 0), right.get(k, 0)) for k in keys) / union if union else 1.0


def style_similarity(left, right):
    if not left and not right:
        return 1.0
    a, b = Counter(left), Counter(right)
    # Explicit frequency-vector total-variation definition, not the style parser.
    distance = sum(abs(a[k] / max(1, len(left)) - b[k] / max(1, len(right))) for k in set(a) | set(b))
    return max(0.0, 1.0 - distance / 2)


def reference_metrics(left, right):
    sequence = lambda a, b: difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    return {"character_similarity": sequence(left[0], right[0]),
            "token_similarity": sequence(left[1], right[1]),
            "identifier_normalized_similarity": sequence(left[3], right[3]),
            "ast_type_similarity": overlap(left[5], right[5]),
            "control_profile_similarity": overlap(left[4], right[4]),
            "identifier_multiset_similarity": overlap(Counter(left[2]), Counter(right[2])),
            "identifier_style_similarity": style_similarity(left[6], right[6])}


class MetricStreamTests(unittest.TestCase):
    def test_hand_specified_tokens_and_source_helpers(self):
        for language, fixtures in FIXTURES.items():
            for source, toks, ids, normalized, controls, syntax, styles in fixtures:
                with self.subTest(language=language, source=source):
                    self.assertEqual(m.tokens(source, language), toks)
                    self.assertEqual(m.identifiers(source, language), ids)
                    self.assertEqual(m._normalized_tokens(source, language), normalized)
                    self.assertEqual(+m._control_profile(source, language), Counter(controls))
                    self.assertEqual(+m._syntactic_profile(source, language), Counter(syntax))
                    self.assertEqual([m._identifier_style(i) for i in ids], styles)

    def test_all_seven_fields_against_fixture_reference(self):
        for language, fixtures in FIXTURES.items():
            for left, right in itertools.product(fixtures, repeat=2):
                with self.subTest(language=language, left=left[0], right=right[0]):
                    self.assertEqual(m.source_metrics(left[0], right[0], language), reference_metrics(left, right))

    def test_stream_helpers_do_not_mutate_tokens(self):
        for language, fixtures in FIXTURES.items():
            for _, toks, ids, normalized, controls, _, _ in fixtures:
                original = list(toks)
                self.assertEqual(m._identifiers_from_tokens(toks, language), ids)
                self.assertEqual(m._normalized_token_stream(toks, language), normalized)
                self.assertEqual(+m._control_from_tokens(toks), Counter(controls))
                self.assertEqual(toks, original)
                self.assertEqual(m._normalized_token_stream(tuple(toks), language), normalized)

    def test_token_reuse_counts_without_timing(self):
        for language, expected in (("python", 2), ("javascript", 4)):
            with patch.object(m, "tokens", wraps=m.tokens) as spy:
                m.source_metrics("x = 1", "y = 2", language)
                self.assertEqual(spy.call_count, expected)

    def test_normalized_and_raw_definitions_remain_distinct(self):
        result = m.source_metrics("x = 400", "x = 800", "python")
        self.assertEqual(result["identifier_normalized_similarity"], 1.0)
        self.assertLess(result["token_similarity"], 1.0)

    def test_other_language_still_uses_javascript_fallback(self):
        left, right = FIXTURES["javascript"][1:3]
        self.assertEqual(m.source_metrics(left[0], right[0], "other"), reference_metrics(left, right))


if __name__ == "__main__":
    unittest.main()
