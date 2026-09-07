# Contributing

Start with a public, minimal failure case and a pinned environment/trainer version.
One adapter with a truthful support matrix is more useful than broad untested claims.

1. Add a synthetic regression test.
2. Make a narrow implementation change.
3. Run `python -m unittest discover -s tests -v` with `PYTHONPATH=src` or an
   editable installation.
4. Run `python scripts/build_release.py` when changing the package or website.
5. Document untested behavior and skipped checks.

Do not contribute private tasksets, screenshots, employer code, credentials, or
third-party material without the necessary rights. Contributions are under MIT.

Factory modules are trusted executable code. EnvPort is not a sandbox. Do not
run untrusted adapters in environments with sensitive credentials or data.
