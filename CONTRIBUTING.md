# Contributing

Issues and pull requests are welcome.

- **Every gate must be able to fail.** A new or changed gate comes with a `--self-test` case that plants the mistake and shows the FAIL, and a clean case that passes.
- **No new dependencies** in `harness/`: it must run on a bare Python 3.11+ with git.
- **Run the checks before opening a PR:** `python3 -m pytest -q` (runs every self-test, the installer end to end, and the hook guard) and `claude plugin validate .` if you have Claude Code.
- Keep agent and skill text short, specific and testable. A rule nobody can check is a wish.
- By contributing you agree your contribution is licensed under Apache-2.0.
