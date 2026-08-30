# Field data

Use this reference when querying or interpreting CrUX or PageSpeed Insights.

## Source choice

Use the CrUX API as the primary source for real-user metrics. PSI is useful for Lighthouse lab output and may expose legacy field blocks, but recurring workflows must not depend on `loadingExperience` or `originLoadingExperience` being present.

The CrUX `QueryRequest` supports one `origin` or `url`, optional `formFactor`, optional `metrics`, and an optional effective-connection-type dimension where supported. It does not return country segmentation or device traffic shares. Use the CrUX BigQuery country datasets when country analysis is genuinely required and available.

## Authentication

Use an API key stored in `PSI_API_KEY`. Never put it in a committed command, script, or captured report. Google APIs commonly carry the key in the query string, so avoid verbose command output and rotate a leaked key.

Do not hardcode quota or billing claims; verify current Google documentation when those details matter.

## CrUX request

Example using an origin and phone form factor:

```bash
curl -sS --max-time 60 -X POST \
  "https://chromeuxreport.googleapis.com/v1/records:queryRecord?key=${PSI_API_KEY}" \
  -H "Content-Type: application/json" \
  --data '{"origin":"https://example.com","formFactor":"PHONE"}' \
  -o crux-phone.json
```

Use `url` instead of `origin` for URL scope; never send both. Query scopes and form factors separately and preserve each label in the report.

For historical trends, use `records:queryHistoryRecord` and verify its current response schema before automating interpretation.

## PSI request

PSI strategies are lab configurations, not a device traffic split:

```bash
curl -sS --max-time 180 -G \
  "https://www.googleapis.com/pagespeedonline/v5/runPagespeed" \
  --data-urlencode "url=https://example.com/" \
  --data-urlencode "strategy=MOBILE" \
  --data-urlencode "key=${PSI_API_KEY}" \
  --data-urlencode "category=PERFORMANCE" \
  -o psi-mobile.json
```

Repeat with `DESKTOP` when it is relevant. A PSI strategy describes the Lighthouse run; it is not the same thing as CrUX `formFactor` data.

## Parse captured responses

```bash
python "{skill-root}/scripts/summarize_field_data.py" crux crux-phone.json
python "{skill-root}/scripts/summarize_field_data.py" psi psi-mobile.json psi-desktop.json
```

Replace `{skill-root}` with the absolute directory containing `SKILL.md`; use `python3` where that is the available command. The parser fails visibly on API errors and labels missing optional blocks instead of treating them as zero. If Python is unavailable, reproduce the same missing-versus-zero behavior with the runtime’s JSON tools.

## Interpretation rules

- Report the collection period supplied by the API.
- Report URL and origin results separately.
- Report p75 and histogram proportions when present; do not infer population share from form-factor-specific records.
- Use current metric thresholds from authoritative documentation rather than copying thresholds into a long-lived skill.
- A missing record means insufficient eligible data for that scope/dimension. Continue with lab and transport evidence.
- CrUX is aggregated over a rolling period and cannot isolate a recent release without additional RUM or experiment data.
- A p75 value describes the threshold at or below which roughly 75% of eligible experiences fall; avoid calling it the average or the typical user.
