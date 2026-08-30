# Transport inspection

Use this reference for HTTP timing, redirects, cache behavior, cookies, and content negotiation.

Adapt syntax to the active shell. On Windows, invoke `curl.exe` when `curl` is aliased to another command.

## Sequential baseline

Run at least three sequential samples:

```bash
curl -sS -L -o /dev/null --max-time 60 \
  -w "dns:%{time_namelookup} connect:%{time_connect} tls:%{time_appconnect} ttfb:%{time_starttransfer} total:%{time_total} bytes:%{size_download} status:%{http_code} redirects:%{num_redirects} final:%{url_effective}\n" \
  "https://example.com/"
```

Report median and range when variability matters. These phases are client-observed timings, not origin-server spans.

## Redirects and headers

Inspect a non-following request first so each hop remains attributable:

```bash
curl -sS -D - -o /dev/null --max-time 30 "https://example.com/"
```

Follow each `Location` deliberately, or capture the full `-L` header stream and separate response blocks by status line. Never attribute a cookie or cache header from an intermediate redirect to the final HTML response.

Check intended canonical variants and locale roots when they are relevant to the reported journey. A fast redirect can still be functionally wrong.

## Cache assessment

Read `Cache-Control`, `Age`, `Vary`, `Set-Cookie`, and vendor cache-status headers together.

Before calling a miss or bypass a fault, establish:

- Whether the method and status are cache-eligible.
- Whether authentication, cookies, locale, consent, experiments, or request headers change the representation.
- Whether the cache key includes the relevant variants.
- Whether a cache rule intentionally bypasses HTML.
- Whether repeated requests reached the same cache layer or point of presence.

One miss is normal. Repeated misses are evidence of observed non-reuse from the test vantage point, not automatically a configuration defect.

A response that sets a cookie may still be cacheable under some CDN configurations, but shared caching is unsafe unless the cached representation is demonstrably user-independent and the cookie behavior is deliberately handled.

Use a cookie-free request only as a controlled comparison:

```bash
curl -sS -D - -o /dev/null --max-time 30 -H "Cookie:" "https://example.com/page"
```

Record the request headers and response differences. Do not assume an empty `Cookie` header reproduces a true first visit when other headers or edge state differ.

## HTML versus static-resource contrast

```bash
curl -sS -o /dev/null --max-time 30 -w "html ttfb:%{time_starttransfer} total:%{time_total}\n" "https://example.com/page"
curl -sS -o /dev/null --max-time 30 -w "asset ttfb:%{time_starttransfer} total:%{time_total}\n" "https://example.com/asset.css"
```

Treat the result as a contrast between two URLs. Separate processes may use different connections, and the URLs may differ in cacheability, routing, computation, size, and origin. A large gap supports further cache/origin investigation but does not isolate a single cause.

## Content negotiation and bytes

If a browser is unavailable, send a realistic `Accept` header when inspecting negotiated images:

```bash
curl -sS -o /dev/null --max-time 30 \
  -H "Accept: image/avif,image/webp,image/apng,*/*" \
  -w "bytes:%{size_download} type:%{content_type}\n" \
  "https://example.com/image"
```

Label curl asset totals as approximations. They do not reproduce responsive-image selection, browser cache/service-worker behavior, or every browser request.

## Session serialization

Test session locking only when response headers or stack evidence indicate server-side sessions and the symptom is concurrent same-user requests. Use a small number of requests and explicit timeouts. Compare independent sessions with one shared test session, repeat the comparison, and avoid production load. A slower shared-session group is evidence consistent with serialization; server tracing is needed to identify the lock implementation.
