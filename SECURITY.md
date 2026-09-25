# Security policy

## Reporting a vulnerability

Please do not open a public issue for security problems.

- Preferred: use GitHub's private vulnerability reporting on this repository
  ("Security" tab, "Report a vulnerability"), if it is enabled.
- Otherwise email **contact@soclose.co** with "elnino-watch security" in the subject.

Include what you found, how to reproduce it, and the impact you see. You will get an
acknowledgement within 7 days and a fix or a decision within 30 days for anything we can
confirm. We are happy to credit you in the release notes if you want.

## What is in scope

- The backend (`backend/app`): the admin gate in public mode (`X-Admin-Token`), the
  security headers and CSP (`app/security.py`), the SEO routes (`app/seo.py`), the webcam
  snapshot proxy (`app/cams_api.py`), the places search / preview endpoints, and anything
  that could let a visitor trigger upstream requests, write data, read the operator's
  preparedness state, or exhaust memory on a small VPS.
- The frontend (`frontend/src`): anything that renders third-party content (news titles,
  social posts, webcam pages) without escaping.
- The deploy kit (`ops/deploy`): the systemd hardening, nginx template and `first_setup.sh`.

## What is out of scope

- Availability or correctness of the upstream data providers.
- Rate limiting of the public demo at https://elnino.soclose.co (it is intentionally
  throttled; a 429 is not a bug).
- Reports produced by automated scanners without a working proof of concept.

## Supported versions

Only the `main` branch is supported. There are no release branches yet.

## Good to know when you look

- Public mode (`PUBLIC_MODE=true`) is the hardened configuration; the default local
  install trusts localhost on purpose (single-user dashboard).
- Tests never touch the network. `backend/scripts/verify_sources.py` is the only thing
  that does, and only when you run it.
- No secret is committed to this repository. Credentials live in `.env` files that are
  ignored by git; see `ops/deploy/env.example`.
