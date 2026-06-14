# Zitadel hosted Login UI branding assets

`scripts/zitadel_bootstrap.py` (`_ensure_branding`) applies the Propel theme to
Zitadel's hosted Login UI v2 via the instance **Label Policy** — colors are
derived from the frontend Tailwind tokens and applied automatically on every
bootstrap (local `docker compose up` and the beta/prod deploy step), so the
login page matches the app with no console steps.

Logos/icons are optional. Drop PNGs here and they are uploaded + activated on the
next bootstrap; if a file is absent, colors-only branding still applies.

| File            | Used for                          |
| --------------- | --------------------------------- |
| `logo.png`      | Login UI logo (light theme)       |
| `logo-dark.png` | Login UI logo (dark theme)        |
| `icon.png`      | Login UI icon/favicon (light)     |
| `icon-dark.png` | Login UI icon/favicon (dark)      |

Recommended: transparent-background PNGs. Zitadel resizes for display.
