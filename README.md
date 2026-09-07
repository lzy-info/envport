# EnvPort · 境枢

Experimental, local-first contract checks for agent environments.

**Status: 0.1.0a1 — functional prototype, not a trainer integration platform.**

EnvPort probes reset behavior, observable instance isolation, explicit no-op/oracle
grading expectations, finite rewards, and a small trajectory schema. It includes
a deliberately broken demo to show what failure looks like. It does not claim
veRL, AndroidWorld, OSWorld, OpenEnv or ATIF compatibility.

## Start here

Requires Python 3.11+. No runtime dependencies. Installing from source needs pip
and setuptools; there is no published PyPI package in this release.

```bash
git clone https://github.com/lzy-info/envport.git
cd envport
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -e .

envport doctor --demo good
envport doctor --demo bad                 # expected exit code 1
envport validate-trajectory examples/trajectory.json
python -m envport doctor --factory examples.custom_factory:make_env
```

Commands may also be run as `python -m envport ...` after installation.
For a completely dependency-free checkout run with `PYTHONPATH=src` on Unix,
or set `$env:PYTHONPATH='src'` in PowerShell first.

`--format json` prints a versioned JSON report. `--output report.json` writes a
new file and refuses to overwrite an existing report. Exit codes: 0 means no
failed checks (inspect skips); 1 means failed checks; 2 means usage/input error.

## What this release actually checks

| Area | Implemented | Not established by a pass |
| --- | --- | --- |
| Environment | Method presence, fresh instances, same-seed observable reset and replay | All hidden state or universal determinism |
| Isolation | One instance's observed state while another is stepped | Parallel load, OS/container isolation |
| Grading | Explicit no-op/oracle thresholds and declared reward bounds | Reward hacking resistance for arbitrary actions |
| Trajectories | Types, aligned array lengths, finite numbers, image-reference metadata | Tokenizer truth, actual image ingestion, gradients, trainer correctness |

Use only trusted local factories. They run **in-process**, with no timeout or
sandbox, and can execute arbitrary code. Never point a probe at production
systems, payment flows, or private customer data. Reports may contain data returned
by your adapter; review before sharing.

## Adapter contract

A zero-argument factory returns a **new** instance implementing `reset(seed)`,
`observe()`, `step(action) -> StepResult`, `grade()` and `close()`.
JSON-compatible observations must exclude volatile timestamps and IDs if you
expect equality checks to be meaningful. `observe()` and `grade()` must not mutate
state. An optional `envport_probe()` returns a `ProbeSpec` with no-op and known
success sequences and numerical bounds. Without it, action checks are skipped.

See [the example factory](examples/custom_factory.py),
[the public contract](src/envport/contract.py), and the Chinese documentation at
`dist/guide.html`. The internal trajectory format is experimental; future adapters
should reuse upstream standards where feasible instead of declaring a new standard.

## Website and GitHub Pages

The website is plain HTML/CSS/JavaScript. Open `dist/index.html` locally or run:

```bash
python scripts/build_release.py
python -m http.server 8000 --directory dist
```

Then open `http://localhost:8000`. The site has no backend, tracking, API keys,
remote fonts, or customer-data forms. Its report switcher displays real, captured
CLI output from the bundled **simulated counter environments**, not a GUI benchmark.

The repository includes `pages.yml` for publication from `dist/`. See
[PUBLISHING.md](PUBLISHING.md) for exact steps. The project repository is
[lzy-info/envport](https://github.com/lzy-info/envport). The expected Pages URL is
`https://lzy-info.github.io/envport/` once Pages is enabled and a deployment succeeds;
repository creation alone does not publish the website. See GitHub's
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
before adding commercial features; project documentation is the intended use.

## Develop and verify

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
node --check dist/assets/app.js
python scripts/build_release.py
```

The release builder regenerates captured reports, checks local site references,
and creates a source download plus a complete ZIP under `release/`. Node is only
needed for the optional JavaScript syntax check, not for the Python tool or site.

## Roadmap, not supported features

- [ ] Choose one real GUI environment and publish a reproducible failure corpus.
- [ ] Implement and test one pinned trainer integration (candidate: veRL).
- [ ] Test image/tensor preservation at that concrete boundary.
- [ ] Add safe process isolation, timeouts, and richer replay after real usage.

No cloud runtime, marketplace, payment system, model API, or private benchmark is
included. If you need an adapter, open an **Adapter request** issue with a public
minimal example; do not post credentials, proprietary screenshots, or customer data.

[Request an adapter](https://github.com/lzy-info/envport/issues/new?template=adapter-request.md).

## License

MIT — see [LICENSE](LICENSE). Original implementation; no employer code or data
is included. Product and framework names identify planned integration targets, not
affiliations, endorsements, or current compatibility.
