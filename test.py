import unittest

from dcsm import DCSMTemplate

class TestDCSMTemplate(unittest.TestCase):
    def test_braced_pattern(self) -> None:
        template = DCSMTemplate("Value: $DCSM{var}")
        self.assertEqual(template.substitute(var="123"), "Value: 123")

    def test_named_pattern(self) -> None:
        template = DCSMTemplate("Name: $DCSM_NAME")
        self.assertEqual(template.substitute(NAME="John"), "Name: John")

    def test_escaped_braced(self) -> None:
        template = DCSMTemplate("Escaped: $$DCSM{VAR}")
        self.assertEqual(template.substitute(), "Escaped: $DCSM{VAR}")

    def test_notpattern(self) -> None:
        template = DCSMTemplate("Not a pattern: $DCSMVAR")
        self.assertEqual(template.substitute(), "Not a pattern: $DCSMVAR")

    def test_escaped_named(self) -> None:
        template = DCSMTemplate("Escaped: $$DCSM_VAR")
        self.assertEqual(template.substitute(), "Escaped: $DCSM_VAR")

    def test_invalid_braced(self) -> None:
        template = DCSMTemplate("Invalid: $DCSM{}")
        self.assertEqual(template.safe_substitute(), "Invalid: $DCSM{}")

    def test_invalid_named(self) -> None:
        template = DCSMTemplate("Invalid: $DCSM_name")
        self.assertEqual(template.safe_substitute(), "Invalid: $DCSM_name")

if __name__ == "__main__":
    unittest.main()
