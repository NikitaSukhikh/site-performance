# Web Performance Audit skill

Use this skill with a command-line or IDE coding assistant to investigate why a
public website is slow. It combines real-user Chrome UX Report (CrUX) data,
PageSpeed Insights, HTTP inspection, and browser measurements.

## What you need

- A coding assistant that can run terminal commands and access the internet.
- `curl` and Python 3.
- [Node.js](https://nodejs.org/) 20 or newer, including `npm`.
- One Google Cloud API key. You do **not** need OAuth credentials or a service
  account.

The commands in `SKILL.md` use Bash syntax and standard Unix tools. On Windows,
run the skill in WSL or Git Bash. Native PowerShell works for the credential setup
below, but an assistant would need to translate the audit commands.

## 1. Install the skill

### From a marketplace

Open the marketplace listing and choose **Install**. If the marketplace asks for
a secret or environment variable, add one named `PSI_API_KEY` using the Google API
key created in step 3.

This is a command-line skill, so allow it to run `curl`, Python, `npm`, and
`playwright-cli`, and to make outbound requests to Google APIs and the website you
ask it to audit.

There is no separate MCP server URL to configure. The marketplace host must be
able to run local shell commands; otherwise, use the GitHub installation in a
command-line or IDE assistant.

### From GitHub

Download or clone the repository, then copy the whole folder—not only
`SKILL.md`—into a skills directory supported by your assistant.

For Codex, use either:

- User installation, available in all projects:
  `~/.agents/skills/web-performance-audit/`
- Repository installation, available in one project:
  `<repository>/.agents/skills/web-performance-audit/`

The resulting folder should contain:

```text
web-performance-audit/
|-- SKILL.md
`-- README.md
```

Codex normally detects a new skill automatically. Restart it if the skill does
not appear when you run `/skills` or type `$web-performance-audit`. For another
assistant or IDE, use its documented skills directory.

## 2. Install the browser tool

Check the basic command-line tools:

```bash
curl --version
python3 --version
node --version
npm --version
```

On Windows, `python --version` may work when `python3 --version` does not. Install
Python 3 and make the `python3` command available because the skill uses that
command in its examples.

Install Microsoft's Playwright CLI:

```bash
npm install -g @playwright/cli@latest
playwright-cli --version
```

Then check that a browser opens:

```bash
playwright-cli open https://example.com
playwright-cli close
```

If the command is not found after installation, open a new terminal and try
again. The official [Playwright CLI guide](https://github.com/microsoft/playwright/blob/main/docs/src/getting-started-cli.md)
also documents a project-local installation if global npm packages are not
allowed on your computer.

## 3. Create the Google API key

One standard Google Cloud API key is used for both Google services.

1. Sign in to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project, or select an existing project that you control.
3. Enable the
   [PageSpeed Insights API](https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com).
4. Enable the
   [Chrome UX Report API](https://console.cloud.google.com/apis/library/chromeuxreport.googleapis.com).
5. Open [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials).
6. Choose **Create credentials > API key**. Create a standard API key; do not bind
   it to a service account.
7. Under **API restrictions**, select **Restrict key**, then allow only:
   **PageSpeed Insights API** and **Chrome UX Report API**.
8. Under **Application restrictions**, use **IP addresses** for a server or CI
   runner with a fixed public IP. For a local laptop whose IP changes, leave this
   restriction unset unless you have another suitable restriction.
9. Save the key and keep it private.

Google recommends restricting API keys and never committing them to a source-code
repository. Quotas and account requirements can change, so check the quota pages
in your Google Cloud project rather than relying on a fixed number in this guide.

## 4. Set `PSI_API_KEY`

Set the key in the same terminal session that launches your assistant.

macOS, Linux, or Git Bash:

```bash
export PSI_API_KEY="PASTE_YOUR_KEY_HERE"
```

PowerShell:

```powershell
$env:PSI_API_KEY = "PASTE_YOUR_KEY_HERE"
```

These commands set the value only for the current terminal session. For repeated
use, add it through your operating system, IDE, CI, or marketplace secret manager.
Do not put the key in `SKILL.md`, a prompt, a screenshot, or a committed `.env`
file.

Check that the variable exists without printing the secret:

macOS, Linux, or Git Bash:

```bash
test -n "$PSI_API_KEY" && echo "PSI_API_KEY is set"
```

PowerShell:

```powershell
if ($env:PSI_API_KEY) { "PSI_API_KEY is set" }
```

## 5. Verify both Google APIs

Run these tests from macOS, Linux, or Git Bash:

```bash
curl -fsS --max-time 180 -G \
  "https://www.googleapis.com/pagespeedonline/v5/runPagespeed" \
  --data-urlencode "url=https://example.com/" \
  --data-urlencode "strategy=mobile" \
  --data-urlencode "key=$PSI_API_KEY" \
  -o /dev/null && echo "PageSpeed Insights API: OK"

curl -fsS --max-time 60 -X POST \
  "https://chromeuxreport.googleapis.com/v1/records:queryRecord?key=$PSI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"origin":"https://web.dev"}' \
  -o /dev/null && echo "Chrome UX Report API: OK"
```

PowerShell:

```powershell
$psiUri = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=https%3A%2F%2Fexample.com%2F&strategy=mobile&key=$env:PSI_API_KEY"
Invoke-RestMethod -Uri $psiUri | Out-Null
"PageSpeed Insights API: OK"

$cruxUri = "https://chromeuxreport.googleapis.com/v1/records:queryRecord?key=$env:PSI_API_KEY"
Invoke-RestMethod -Method Post -Uri $cruxUri -ContentType "application/json" -Body '{"origin":"https://web.dev"}' | Out-Null
"Chrome UX Report API: OK"
```

If a request fails:

| Error | Usually means |
|---|---|
| `401` or `403` | The key is invalid, an API is not enabled, or a key restriction does not match. |
| `404` from CrUX | The requested page or origin has too little eligible real-user data. Try a well-known public origin. |
| `429` | The project has reached an API quota or rate limit. Check **APIs & Services > Quotas**. |
| `playwright-cli: command not found` | Reopen the terminal or fix npm's global executable path. |

## 6. Run your first audit

```bash
/web-performance-audit https://example.com/
```

Only audit sites you are authorized to test. Measurements create normal web
traffic, and browser runs may write local reports or temporary files in the working
directory.

## Updating or removing the skill

- Marketplace: use the listing's **Update** or **Uninstall** action.
- GitHub: pull/download the latest version and replace the installed skill folder.
  Delete that folder to uninstall it.
- Rotate the Google API key if it is exposed. Remove keys you no longer use.

## Official references

- [PageSpeed Insights API: get started](https://developers.google.com/speed/docs/insights/v5/get-started)
- [Chrome UX Report API](https://developer.chrome.com/docs/crux/api)
- [Google Cloud API key management](https://cloud.google.com/docs/authentication/api-keys)
- [Google Cloud API key security](https://cloud.google.com/docs/authentication/api-keys-best-practices)
- [OpenAI: build and install skills](https://developers.openai.com/codex/skills)
- [Microsoft Playwright CLI for coding agents](https://github.com/microsoft/playwright/blob/main/docs/src/getting-started-cli.md)
