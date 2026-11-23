# Mar & Pesca Assistant — first backend step

This is a separate Worker. It does not modify the existing `mar-pesca-api` Worker or the site's weather-data endpoints.

## What this first version does

- Exposes `GET /api/health` and `POST /api/chat`.
- Uses Cloudflare Workers AI with `@cf/meta/llama-3.1-8b-instruct-fp8-fast`.
- Supports Spanish, English, French and Arabic.
- Supports a supplied `context` object containing the current Mar & Pesca forecast/tide/wave values.
- Stores successful answers in a shared KV namespace for 30 minutes by default.
- Reuses an answer only when the normalized question, language, location, date and supplied data context match.
- Does not invent live weather or marine values when no context is supplied.
- Does not include conversation history in the shared cache, so one visitor's private conversation is not mixed with another's.

This is the backend foundation only. The website chat interface and the adapter that supplies the page's normalized live data are a separate next step.

## Configure

1. From this directory, create a KV namespace:
   `npx wrangler kv namespace create ASSISTANT_CACHE`
2. Replace `REPLACE_WITH_KV_NAMESPACE_ID` in `wrangler.jsonc` with the returned ID.
3. Confirm the `ALLOWED_ORIGIN` matches the live website's exact origin.
4. Deploy this Worker separately:
   `npx wrangler deploy`

The Worker needs the Cloudflare Workers AI binding named `AI` and the KV binding named `ASSISTANT_CACHE`.

## Request example

```json
{
  "question": "¿Mañana será buen día para pescar en Martil?",
  "language": "es",
  "location": "martil",
  "date": "2026-11-24",
  "context": {
    "weather": {},
    "tides": {},
    "waves": {}
  }
}
```

The context fields above are illustrative. The website adapter must send the real normalized values loaded by Mar & Pesca.

## Cache behavior

The cache key includes a stable hash of the normalized question and all context data. Therefore, a material forecast change produces a different cache key rather than reusing an answer based on old conditions. The TTL is 30 minutes by default and can be adjusted with `CACHE_TTL_SECONDS`.

Equivalent wording is not yet semantically matched: punctuation, case and accents are normalized, but substantially different phrasings may produce separate cache entries. Semantic matching and protection against simultaneous cache misses can be added after the first end-to-end integration is validated.
