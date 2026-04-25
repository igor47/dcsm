import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dcsm import (
    GITIGNORE_BEGIN,
    GITIGNORE_END,
    DCSMTemplate,
    Files,
    find_proximate_gitignore,
    gitignore,
    update_gitignore,
)


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


class TestGitignore(unittest.TestCase):
    def _touch(self, path: Path, content: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_find_proximate_uses_existing_root_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._touch(root / ".gitignore", "something\n")
            template = root / "sub" / "dir" / "file.env.template"
            self._touch(template)

            found = find_proximate_gitignore(template, root)
            self.assertEqual(found, root / ".gitignore")

    def test_find_proximate_prefers_closest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._touch(root / ".gitignore")
            self._touch(root / "sub" / ".gitignore")
            template = root / "sub" / "dir" / "file.env.template"
            self._touch(template)

            found = find_proximate_gitignore(template, root)
            self.assertEqual(found, root / "sub" / ".gitignore")

    def test_find_proximate_rejects_template_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "inside"
            root.mkdir()
            outside = Path(td) / "elsewhere" / "file.env.template"
            self._touch(outside)

            with self.assertRaises(ValueError):
                find_proximate_gitignore(outside, root)

    def test_find_proximate_falls_back_to_template_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = root / "sub" / "dir" / "file.env.template"
            self._touch(template)

            found = find_proximate_gitignore(template, root)
            self.assertEqual(found, root / ".gitignore")
            self.assertFalse(found.exists())

    def test_find_proximate_when_template_is_in_template_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = root / "app.env.template"
            self._touch(template)

            # no gitignore present -> falls back to template_root/.gitignore
            self.assertEqual(
                find_proximate_gitignore(template, root),
                root / ".gitignore",
            )

            # with a gitignore present at the root, that's also what's found
            self._touch(root / ".gitignore")
            self.assertEqual(
                find_proximate_gitignore(template, root),
                root / ".gitignore",
            )

    def test_gitignore_command_renders_paths_relative_to_each_gitignore(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # root .gitignore handles templates with no closer ancestor
            self._touch(root / ".gitignore")
            self._touch(root / "config" / "postgres" / "init.sh.template")
            # synapse has its own .gitignore, so its template stays local to it
            self._touch(root / "config" / "synapse" / ".gitignore")
            self._touch(root / "config" / "synapse" / "homeserver.yaml.template")
            self._touch(root / "config" / "synapse" / "log.config.template")

            with mock.patch.dict(
                os.environ, {"DCSM_TEMPLATE_DIR": str(root)}, clear=True
            ):
                gitignore(Files())

            root_lines = (root / ".gitignore").read_text().splitlines()
            synapse_lines = (
                (root / "config" / "synapse" / ".gitignore").read_text().splitlines()
            )

            # exactly one entry in root .gitignore, with full path from root
            self.assertIn("config/postgres/init.sh", root_lines)
            self.assertNotIn("init.sh", root_lines)
            self.assertNotIn("homeserver.yaml", root_lines)
            self.assertNotIn("config/synapse/homeserver.yaml", root_lines)

            # synapse entries are bare filenames (relative to that gitignore)
            self.assertIn("homeserver.yaml", synapse_lines)
            self.assertIn("log.config", synapse_lines)
            self.assertNotIn("config/synapse/homeserver.yaml", synapse_lines)

    def test_gitignore_command_collects_into_one_file_when_none_exist(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._touch(root / "a" / "one.env.template")
            self._touch(root / "b" / "c" / "two.yaml.template")

            with mock.patch.dict(
                os.environ, {"DCSM_TEMPLATE_DIR": str(root)}, clear=True
            ):
                gitignore(Files())

            # only one gitignore should be created, at the template root
            self.assertTrue((root / ".gitignore").is_file())
            self.assertFalse((root / "a" / ".gitignore").exists())
            self.assertFalse((root / "b" / "c" / ".gitignore").exists())

            content = (root / ".gitignore").read_text()
            self.assertIn("a/one.env", content)
            self.assertIn("b/c/two.yaml", content)

    def test_update_gitignore_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".gitignore"
            wrote = update_gitignore(path, ["foo.env", "bar.yaml"])
            self.assertTrue(wrote)
            content = path.read_text()
            self.assertIn(GITIGNORE_BEGIN, content)
            self.assertIn(GITIGNORE_END, content)
            self.assertIn("bar.yaml", content)
            self.assertIn("foo.env", content)
            # entries are sorted
            self.assertLess(content.index("bar.yaml"), content.index("foo.env"))

    def test_update_gitignore_appends_block_to_existing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".gitignore"
            path.write_text("node_modules/\n*.log\n")
            update_gitignore(path, ["app.env"])
            content = path.read_text()
            # original content preserved
            self.assertTrue(content.startswith("node_modules/\n*.log\n"))
            self.assertIn(GITIGNORE_BEGIN, content)
            self.assertIn("app.env", content)

    def test_update_gitignore_replaces_existing_block(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".gitignore"
            path.write_text(f"keep-me\n\n{GITIGNORE_BEGIN}\nold.env\n{GITIGNORE_END}\n")
            update_gitignore(path, ["new.env"])
            content = path.read_text()
            self.assertIn("keep-me", content)
            self.assertNotIn("old.env", content)
            self.assertIn("new.env", content)
            # only one managed block
            self.assertEqual(content.count(GITIGNORE_BEGIN), 1)

    def test_update_gitignore_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / ".gitignore"
            self.assertTrue(update_gitignore(path, ["a", "b"]))
            self.assertFalse(update_gitignore(path, ["a", "b"]))
            self.assertFalse(update_gitignore(path, ["b", "a"]))

    def test_gitignore_command_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._touch(root / ".gitignore", "pre-existing\n")
            self._touch(root / "config" / "postgres" / "init.sh.template")
            self._touch(root / "config" / "synapse" / "homeserver.yaml.template")
            self._touch(root / "config" / "synapse" / ".gitignore")

            with mock.patch.dict(
                os.environ, {"DCSM_TEMPLATE_DIR": str(root)}, clear=True
            ):
                gitignore(Files())

            root_ignore = (root / ".gitignore").read_text()
            self.assertIn("pre-existing", root_ignore)
            self.assertIn("config/postgres/init.sh", root_ignore)
            self.assertNotIn("homeserver.yaml", root_ignore)

            synapse_ignore = (root / "config" / "synapse" / ".gitignore").read_text()
            self.assertIn("homeserver.yaml", synapse_ignore)


if __name__ == "__main__":
    unittest.main()
