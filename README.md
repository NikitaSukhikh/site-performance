# Web Performance Audit skill

This Codex skill investigates website and user-journey performance using Chrome UX Report field data, HTTP transport inspection, and browser measurements. It separates direct observations from inferences and hypotheses so that reports do not overstate what synthetic evidence proves.

## Package contents

```text
web-performance-audit/
|-- SKILL.md
|-- references/
|   |-- browser-measurement.md
|   |-- field-data.md
|   `-- transport.md
`-- scripts/
    |-- playwright_observe.js
    |-- playwright_read.js
    |-- summarize_field_data.py
    `-- test_summarize_field_data.py
```

Install the whole folder so the skill can load its references and reusable scripts.

## Requirements

- A Codex environment with terminal and internet access.
- Python 3.9 or newer for the field-data parser.
- `curl` or an equivalent HTTP client for transport inspection.
- An existing browser/DevTools integration or Playwright CLI for browser measurement.
- A Google API key with the PageSpeed Insights API and Chrome UX Report API enabled when field data is required.

The skill adapts commands to the active shell. On Windows, use `curl.exe` when PowerShell aliases `curl` to another command.

## Install for Codex

Copy the folder into a supported skills directory described in the current [OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills). For a user-scoped installation, name the installed directory `web-performance-audit`.

Codex normally discovers installed skills automatically. Invoke it explicitly with `$web-performance-audit` when needed.

## Browser tooling

Prefer a browser tool that is already configured. Check an existing Playwright CLI installation with:

```bash
playwright-cli --version
```

If the repository already contains Playwright, the upstream CLI supports using the local installation through `npx playwright cli`. If installation is necessary, verify the current upstream instructions, pin the selected version, and record it in the audit. Do not globally install an unpinned `@latest` dependency as part of an ordinary audit.

See [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli) for current installation and configuration details.

## Google API key

Create a standard Google Cloud API key, enable the PageSpeed Insights API and Chrome UX Report API, and restrict the key to those APIs where practical. Account requirements and quotas can change; check the current Google Cloud console rather than relying on a fixed quota in this repository.

Set the key in the terminal session that launches Codex.

macOS, Linux, or Git Bash:

```bash
export PSI_API_KEY="PASTE_YOUR_KEY_HERE"
```

PowerShell:

```powershell
$env:PSI_API_KEY = "PASTE_YOUR_KEY_HERE"
```

Do not commit the key, place it in prompts or screenshots, or print it during diagnostics. Google API keys commonly travel in query strings and can appear in verbose logs.

## Verify the parser

From the skill directory:

```bash
python -m unittest discover -s scripts -p "test_*.py" -v
python scripts/summarize_field_data.py --help
```

## Use

Ask Codex to audit a public URL and name the actual journey or symptom, for example:

```text
Use $web-performance-audit to diagnose why product-list navigation is slow on https://example.com/. Compare first-load and menu-click behavior without load testing the site.
```

Only test sites and journeys you are authorized to access. The skill defaults to low-volume diagnostics and treats authenticated or destructive flows as out of scope unless explicitly authorized.

## Authoritative references

- [OpenAI: build and install skills](https://learn.chatgpt.com/docs/build-skills)
- [Chrome UX Report API](https://developer.chrome.com/docs/crux/api)
- [PageSpeed Insights API](https://developers.google.com/speed/docs/insights/v5/get-started)
- [Google Cloud API-key guidance](https://cloud.google.com/docs/authentication/api-keys)
- [Microsoft Playwright CLI](https://github.com/microsoft/playwright-cli)
