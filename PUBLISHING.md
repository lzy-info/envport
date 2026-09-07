# Publish EnvPort on GitHub Pages

Project repository: [lzy-info/envport](https://github.com/lzy-info/envport).
Uploading the code does not enable GitHub Pages or verify a live URL.

## 1. Prepare the repository

The repository already exists. The owner should review the intended public
contents, then use **Settings → General → Danger Zone → Change repository
visibility → Make public** if the repository is still private. Visibility is not
changed by the supplied workflow. The Pages job deliberately skips private
repositories to avoid publishing their contents accidentally.

To work locally, with Git installed and your normal GitHub authentication:

```bash
git clone https://github.com/lzy-info/envport.git
cd envport
```

Replace the owner/name if you choose another repository. Do not embed access
tokens in commands or remote URLs. You may use GitHub Desktop instead.

## 2. Enable Pages

Go to **Settings → Pages → Build and deployment → Source → GitHub Actions**.
No additional template is needed: `.github/workflows/pages.yml` is included.

If the first automatic deployment was skipped or ran before Pages was enabled, open **Actions →
GitHub Pages → Run workflow**, select `main`, and run it again. Wait for its
deployment job to succeed; use the URL reported there or in Settings → Pages.

For `lzy-info/envport`, the expected URL is `https://lzy-info.github.io/envport/`.
That is an expected address, not a claim that the site is live. A custom domain is
optional. Website asset URLs are relative so project subpaths work.

## 3. Update

```bash
python scripts/build_release.py
git add .
git commit -m "Update EnvPort"
git push
```

The Pages workflow runs the Python tests, regenerates the source download/report
fixtures, and publishes only `dist/`; it does not expose `.github`, tests or local
working files as static routes. The source archive intentionally contains the
open-source code and documentation.

The downloadable source archive excludes itself to avoid recursive packaging.
After unpacking that inner archive, run `python scripts/build_release.py` before
hosting the website to recreate its download link.

## Constraints

- GitHub Pages is static hosting: no Python service or training runs execute there.
- Keep this site focused on the open-source project and documentation. Pages is
  not intended for commercial SaaS, e-commerce, or sensitive transactions.
- Do not add secrets, real customer traces, production screenshots, or employer
  material to a public repository.
- New deployments depend on GitHub account/repository settings and permissions.

Official references:

- [What is GitHub Pages?](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [Custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Usage limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
