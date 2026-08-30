# Field data

Use this reference when querying or interpreting CrUX or PageSpeed Insights.

## Source choice

Use the CrUX API as the primary source for real-user metrics. PSI is useful for Lighthouse lab output and may expose legacy field blocks, but recurring workflows must not depend on `loadingExperience` or `originLoadingExperience` being present.

The CrUX `QueryRequest` supports one `origin` or `url`, optional `formFactor`, optional `metrics`, and an optional effective-connection-type dimension where supported. It does not return country segmentation or device traffic shares. Use the CrUX BigQuery country datasets when country analysis is genuinely required and available.

## Authentication and setup

PageSpeed Insights can run without an API key. Direct CrUX and CrUX History API queries require a Google Cloud API key enabled for the Chrome UX Report API. When a key is available, the secret contract is one exact environment variable: `PSI_CRUX_API_KEY`. The host, operator, or secret manager must inject it into the process that launches the agent. The skill does not discover secret values from frontmatter, the filesystem, or the user’s local machine.

Use the bundled client for API calls. It reads `PSI_CRUX_API_KEY` internally when present, so the agent’s command contains neither the variable name as an argument nor its expanded value. It also redacts the key if Google unexpectedly echoes it in a successful or failed response.

Do not enumerate environment variables, search `.env` files, inspect keychains, or ask the user to paste the key into chat. If a direct CrUX request reports that `PSI_CRUX_API_KEY` is unavailable:

1. State that direct CrUX is unavailable, not that the entire field or PSI layer is unavailable.
2. Continue with anonymous PSI, transport, and browser work. Treat PSI field blocks as optional because Google may omit them.
3. Give the user the relevant setup command below and explain that the agent must be launched again from that same terminal so it inherits the variable.

macOS, Linux, or Git Bash (input is hidden):

```bash
printf "Google API key: "; read -rs PSI_CRUX_API_KEY; printf "\n"; export PSI_CRUX_API_KEY
```

Windows PowerShell (input is hidden):

```powershell
$secureKey = Read-Host "Google API key" -AsSecureString; $env:PSI_CRUX_API_KEY = [System.Net.NetworkCredential]::new("", $secureKey).Password; Remove-Variable secureKey
```

After setting the variable, start `codex` or `claude` from that terminal. For a desktop or hosted agent, use that host’s secret/environment settings and relaunch it. The user can create and enable the required key by following the [official CrUX API key instructions](https://developer.chrome.com/docs/crux/api#crux-api-key).

Do not hardcode quota or billing claims; verify current Google documentation when those details matter.

## Fetch with the bundled client

Replace `{skill-root}` with the absolute directory containing `SKILL.md`; use `python3` where that is the available command.

Check whether direct CrUX access is configured without printing the value:

```bash
python "{skill-root}/scripts/fetch_google_data.py" check-key
```

The command exits successfully only when `PSI_CRUX_API_KEY` is non-empty. It never prints the value. This check is not a prerequisite for anonymous PSI.

CrUX origin record for phones:

```bash
python "{skill-root}/scripts/fetch_google_data.py" crux \
  --origin "https://example.com" \
  --form-factor PHONE \
  --output crux-phone.json
```

CrUX URL record:

```bash
python "{skill-root}/scripts/fetch_google_data.py" crux \
  --url "https://example.com/page" \
  --output crux-url.json
```

CrUX history:

```bash
python "{skill-root}/scripts/fetch_google_data.py" crux-history \
  --origin "https://example.com" \
  --form-factor DESKTOP \
  --output crux-history-desktop.json
```

PSI mobile performance run:

```bash
python "{skill-root}/scripts/fetch_google_data.py" psi \
  --url "https://example.com/" \
  --strategy MOBILE \
  --category PERFORMANCE \
  --output psi-mobile.json
```

PSI runs anonymously when `PSI_CRUX_API_KEY` is absent and automatically uses the key when it is present. Anonymous PSI is suitable for occasional use; if Google rejects or throttles it, configure the key and retry once.

The client validates HTTP(S) targets, rejects credentials embedded in URLs, caps responses at 64 MiB, verifies JSON, writes atomically, and refuses to replace an existing file unless `--force` is explicit. Prefer a new output file for each sample so evidence is preserved.

Use `--origin` or `--url` for CrUX, never both. Query scopes and form factors separately and preserve each label in the report. A PSI strategy describes the Lighthouse run; it is not the same thing as CrUX `formFactor` data.

If Python cannot run, use an equivalent host-provided secret binding and HTTP client that keeps the value out of the agent transcript. Do not fall back to placing the literal key in a generated URL or command.

## Parse captured responses

```bash
python "{skill-root}/scripts/summarize_field_data.py" crux crux-phone.json
python "{skill-root}/scripts/summarize_field_data.py" psi psi-mobile.json psi-desktop.json
```

The parser fails visibly on API errors and labels missing optional blocks instead of treating them as zero. If Python is unavailable, reproduce the same missing-versus-zero behavior with the runtime’s JSON tools.

## Interpretation rules

- Report the collection period supplied by the API.
- Report URL and origin results separately.
- Report p75 and histogram proportions when present; do not infer population share from form-factor-specific records.
- Use current metric thresholds from authoritative documentation rather than copying thresholds into a long-lived skill.
- A missing record means insufficient eligible data for that scope/dimension. Continue with lab and transport evidence.
- CrUX is aggregated over a rolling period and cannot isolate a recent release without additional RUM or experiment data.
- A p75 value describes the threshold at or below which roughly 75% of eligible experiences fall; avoid calling it the average or the typical user.
