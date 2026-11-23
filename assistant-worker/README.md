# Mar & Pesca Assistant Worker

Independent Cloudflare Worker for the Mar & Pesca fishing assistant.

## Endpoints

- `GET /api/health` — reports Worker, Workers AI binding, KV binding, model and code version.
- `POST /api/chat` — accepts a question from the website and returns an answer.

## Runtime

- Cloudflare Workers AI binding: `AI`
- Model: `@cf/meta/llama-3.1-8b-instruct-fast`
- Cache binding: `ASSISTANT_CACHE`
- Cache TTL: 1800 seconds by default.
- Website origin: `https://mar-y-pesca.bestgold8899.workers.dev`

The previous FP8 model identifier has been replaced with the active `-fast` model variant. The website interface continues to call this Worker at `/api/chat`; its request fields are `question`, `language`, `location`, `date` and `context`.

## Deploy

From this directory:

```bash
npx wrangler deploy
```

The Worker needs the Workers AI binding and the KV namespace configured in `wrangler.jsonc`. Do not create a new KV namespace unless the existing namespace is unavailable; the configured namespace is the assistant cache.

## Health check

```
https://mar-pesca-assistant.bestgold8899.workers.dev/api/health
```

Expected health response includes `ok: true`, `aiConfigured: true`, `cacheConfigured: true`, and the model identifier above.

## Request contract

```json
{
  "question": "¿Cómo está el viento mañana?",
  "language": "es",
  "location": "mdiq",
  "date": "2026-11-25",
  "context": {}
}
```

The assistant must not invent forecast or marine values. If the required live data is absent, it says so clearly.