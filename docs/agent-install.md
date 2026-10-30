# Installing nonoclaude: agent guide

You are installing nonoclaude on the user's machine. It writes to their home directory: a launcher in `~/.local/bin`, a profile in `~/.config/nono`, and one line in a shell rc file. Work through the steps in order. Each step ends on a **done when** line; move on only when it holds.

For what the profile keys mean and how to grant extra paths, see the [README](../README.md#configuration). This guide covers installation only.

## 1. Preflight

Collect these facts by running commands. Don't assume any of them:

| Fact | How |
| --- | --- |
| Platform | `uname -s`: `Linux` or `Darwin`. Anything else is unsupported, so stop and tell the user. |
| Landlock (Linux) | `/sys/kernel/security/lsm` contains `landlock`. If it's missing, nono can't enforce anything, so stop. |
| Login shell | `$SHELL`. The installer edits `${ZDOTDIR:-$HOME}/.zshrc` for zsh and `~/.bashrc` for everything else. |
| Dependencies | `python3 -c ''`, `nono --version`, `claude --version`. |
| Existing install | `~/.local/bin/nonoclaude`, `${XDG_CONFIG_HOME:-$HOME/.config}/nono/claude-dev.json`, and any `# nonoclaude` line in the rc file. |
| Existing `claude` wrapper | `grep -n 'claude()' <rc file>` and `alias claude`. |
| Your own sandbox | Whether you can write to `~/.local/bin` and the rc file. If you are running inside nonoclaude or another sandbox, you can't. |

If something is missing, give the user the install command: nono is `brew install nono` on macOS, otherwise see <https://docs.nono.sh/cli/getting_started/installation>; Claude Code is at <https://code.claude.com/docs/en/setup>. Installing system packages is the user's decision.

**Done when** every row has an observed answer and the platform and dependencies pass.

## 2. Agree on choices

The installer asks two yes/no questions, both defaulting to yes:

1. **known_hosts**: let the agent read `~/.ssh/known_hosts`, which Git over SSH needs. The installer only asks this when it creates a new profile; an existing profile is left untouched.
2. **Shell integration**: append a `source` line to the rc file so that plain `claude` is sandboxed inside projects and runs unsandboxed in `~`, in `/tmp`, for management subcommands, and with `--no-sandbox`.

Tell the user what you found in step 1 that changes the outcome:

- An existing `~/.local/bin/nonoclaude` will be overwritten.
- An existing `claude()` function or alias in the rc file will be overridden, because the integration line is appended after it. Offer to remove the old definition.
- On macOS: support is untested on a real Mac, and the sandboxed agent can use the login Keychain, because Claude Code stores its login there.
- On macOS with bash as the login shell: login shells read `~/.bash_profile`, not `~/.bashrc`, so the integration needs a `source ~/.bashrc` there.

Ask with your question tool if you have one, otherwise in plain text. Skip the known_hosts question when a profile already exists, since the installer won't change it. Use the defaults (yes to both) only if the user tells you to choose.

**Done when** each question has an answer from the user, or the user has explicitly told you to use the defaults, and the user has acknowledged each finding that applies.

## 3. Install

Turn the answers into flags. Always pass `--yes`: it stops the installer from prompting, and `install.sh` reads prompt answers from `/dev/tty`, so it ignores anything piped on stdin. Then add a flag for each "no":

| Answer | Flag |
| --- | --- |
| known_hosts: no | `--no-known-hosts` |
| shell integration: no | `--no-shell-integration` |

```sh
bash install.sh --yes [flags]                       # from a checkout
curl -fsSL https://raw.githubusercontent.com/Glaicer/nonoclaude/main/install.sh | bash -s -- --yes [flags]
```

If you are sandboxed (see preflight), give the user the exact command instead. In Claude Code they can type it after `!`.

Run it as the regular user, never with `sudo`. The installer exits nonzero on the first failure and isn't transactional, so read the error, check what it already installed, fix the cause, and run it again. Re-running is safe.

**Done when** the installer prints `nonoclaude: done.`, which comes right after its own sandboxed `nonoclaude --version` check succeeds.

## 4. Activate

- Check that `~/.local/bin` is on `PATH`. If not, tell the user the exact line to add to their rc file.
- Sourcing the rc file in your own shell doesn't change the user's open terminals, so ask them to open a new terminal.
- If `claude auth status` shows they aren't logged in, the user runs `claude auth login`. With the integration, it always runs unsandboxed. Keep credentials out of the chat and out of files.

**Done when** the user confirms a new terminal, `command -v nonoclaude` resolves, and Claude is authenticated.

## 5. Verify

Run this from a scratch project under `~/.cache`. Only the project grant makes that directory writable, unlike `/tmp`, which is writable anyway. It makes one small Haiku request, so get the user's agreement first:

```sh
mkdir -p ~/.cache/nonoclaude-check/project && cd ~/.cache/nonoclaude-check/project
nonoclaude -p 'Run these two commands separately and report each result: touch ~/.nonoclaude-probe ; touch ./probe' --model haiku
ls ~/.nonoclaude-probe ./probe
```

The sandbox is enforcing when:

- `~/.nonoclaude-probe` does **not** exist, because the write outside the project was denied
- `./probe` **does** exist, because the project is writable
- the session started already logged in. On macOS this is the check that the Keychain grant works.

If the session starts logged out on macOS, or a tool fails on a path it needs, collect the exact error and suggest that the user open an issue. Don't widen the profile to work around it unless the user asks.

**Done when** all three conditions hold. Afterwards, delete `~/.cache/nonoclaude-check`, and `~/.nonoclaude-probe` if it was created.

## 6. Report

Tell the user:

- what was installed, and where (launcher, profile, rc file)
- the answers you used for both questions
- the verification results as observed, keeping three outcomes separate: the launcher is installed, an authenticated session starts, and writes outside the project are denied
- any steps still left for them, such as a new terminal, logging in, or a `.bash_profile` edit
