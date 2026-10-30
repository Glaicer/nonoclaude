import json
import os
import subprocess
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
loader = SourceFileLoader("nonoclaude", str(ROOT / "nonoclaude"))
nonoclaude = module_from_spec(spec_from_loader("nonoclaude", loader))
loader.exec_module(nonoclaude)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name).resolve()
        self.project = self.home / "project"
        for path in [self.project, self.home / ".ssh", self.home / ".claude"]:
            path.mkdir()
        (self.home / ".ssh/id_ed25519").write_text("key")
        (self.home / ".ssh/known_hosts").write_text("hosts")
        (self.home / "notes.txt").write_text("notes")
        env = {"HOME": str(self.home)}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def profile(self, **settings):
        base = {
            "read": [str(self.home)],
            "write": ["$HOME/.claude"],
            "exclude": ["$HOME/.ssh"],
        }
        return nonoclaude.make_profile({**base, **settings}, self.project)

    def test_excluded_paths_are_not_readable_but_siblings_are(self):
        read = self.profile()["filesystem"]["read"]
        self.assertNotIn(str(self.home), read)
        self.assertNotIn(str(self.home / ".ssh"), read)
        self.assertIn(str(self.home / "notes.txt"), read)
        self.assertIn(str(self.project), read)

    def test_read_exception_reopens_one_excluded_file(self):
        read = self.profile(read_exceptions=["$HOME/.ssh/known_hosts"])["filesystem"][
            "read"
        ]
        self.assertIn(str(self.home / ".ssh/known_hosts"), read)
        self.assertNotIn(str(self.home / ".ssh/id_ed25519"), read)

    def test_project_and_claude_state_are_writable(self):
        allow = self.profile()["filesystem"]["allow"]
        self.assertEqual(allow, [str(self.home / ".claude"), str(self.project)])

    def test_refuses_home_as_project(self):
        with self.assertRaisesRegex(ValueError, "project directory"):
            nonoclaude.make_profile({"read": [], "write": [], "exclude": []}, self.home)

    def test_refuses_excluded_project(self):
        with self.assertRaisesRegex(ValueError, "excluded"):
            self.profile(exclude=["$HOME/project"])

    def test_refuses_writable_nono_state(self):
        with self.assertRaisesRegex(ValueError, "nono state"):
            self.profile(write=["$HOME/.nono"])

    def test_linux_profile_does_not_touch_the_keychain(self):
        with patch.object(nonoclaude.sys, "platform", "linux"):
            profile = self.profile()
        self.assertNotIn("include", profile["groups"])
        self.assertNotIn("bypass_protection", profile["filesystem"])

    def test_macos_profile_reaches_keychain_only_through_nono_group(self):
        keychains = self.home / "Library/Keychains"
        keychains.mkdir(parents=True)
        (self.home / "Library/Preferences").mkdir()
        settings = json.loads((ROOT / "profile.macos.json").read_text())
        with patch.object(nonoclaude.sys, "platform", "darwin"):
            profile = nonoclaude.make_profile(settings, self.project)
        self.assertEqual(profile["groups"]["include"], ["claude_code_macos"])
        self.assertIn("system_read_macos", profile["groups"]["exclude"])
        self.assertEqual(
            profile["filesystem"]["bypass_protection"], ["$HOME/Library/Keychains"]
        )
        read = profile["filesystem"]["read"]
        self.assertIn(str(self.home / "Library/Preferences"), read)
        self.assertFalse(any(nonoclaude.within(Path(p), keychains) for p in read))
        path = self.home / "profile.json"
        path.write_text(json.dumps(profile))
        result = subprocess.run(
            ["nono", "-s", "profile", "validate", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ShellIntegrationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ["claude", "nonoclaude"]:
            stub = self.bin / name
            stub.write_text(f'#!/bin/sh\necho "{name} $PWD $*"\n')
            stub.chmod(0o755)
        self.project = self.root / "project"
        self.project.mkdir()

    def run_claude(self, shell, cwd, *args):
        script = f'. "{ROOT / "claude.sh"}"; cd "$1"; shift; claude "$@"'
        env = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.root)}
        return subprocess.run(
            [shell, "-c", script, shell, str(cwd), *args],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def test_routing(self):
        cases = [
            (self.project, ["-p", "hi"], f"nonoclaude {self.project} -p hi"),
            (self.project, ["--no-sandbox", "-c"], f"claude {self.project} -c"),
            (self.project, ["mcp", "list"], f"claude {self.project} mcp list"),
            (self.root, [], "claude /tmp"),
            (self.root, ["-c"], f"claude {self.root} -c"),
            (Path("/tmp"), ["-c"], "claude /tmp -c"),
        ]
        for shell in ["bash", "zsh"]:
            for cwd, args, expected in cases:
                with self.subTest(shell=shell, args=args, cwd=cwd):
                    self.assertEqual(self.run_claude(shell, cwd, *args), expected)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name).resolve()
        stubs = self.home / "stubs"
        stubs.mkdir()
        for name in ["nono", "claude"]:
            stub = stubs / name
            stub.write_text("#!/bin/sh\nexit 0\n")
            stub.chmod(0o755)
        self.env = {
            "HOME": str(self.home),
            "SHELL": "/bin/zsh",
            "PATH": f"{stubs}:/usr/bin:/bin",
        }
        self.settings = self.home / ".config/nono/claude-dev.json"
        self.rc = self.home / ".zshrc"

    def install(self, *args):
        return subprocess.run(
            ["bash", str(ROOT / "install.sh"), *args],
            cwd=ROOT,
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_yes_accepts_both_defaults(self):
        result = self.install("--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(self.settings.read_text())
        self.assertEqual(settings["read_exceptions"], ["$HOME/.ssh/known_hosts"])
        self.assertIn("# nonoclaude", self.rc.read_text())

    def test_flags_decline_each_choice(self):
        result = self.install("--yes", "--no-known-hosts", "--no-shell-integration")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("read_exceptions", json.loads(self.settings.read_text()))
        self.assertFalse(self.rc.exists())
        self.assertTrue((self.home / ".local/bin/nonoclaude").exists())

    def test_rejects_unknown_flag(self):
        result = self.install("--yes", "--bogus")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage", result.stderr)
        self.assertFalse(self.settings.exists())


if __name__ == "__main__":
    unittest.main()
