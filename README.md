# ApplyPilot

A job-search workspace with a Next.js/React product site, interactive Three.js artwork, and a dashboard for role analysis, profile evidence, editable outreach drafts, and a browser-saved pipeline.

## Hosted dashboard (`web/`)

Deploy `web` as a Next.js project on Vercel. The free preview works immediately and makes no model calls. To activate AI, add these **server-side** Vercel environment variables and redeploy:

- `OPENAI_API_KEY`: your paid OpenAI API key
- `APPLYPILOT_ENABLE_PAID_API=true`: explicit paid usage activation
- `APPLYPILOT_ACCESS_TOKEN`: a long random workspace password; enter this in the dashboard when using AI mode
- `APPLYPILOT_MODEL=gpt-4.1-mini`: optional model selection

Never use NEXT_PUBLIC variables for credentials. API keys never reach the browser. The workspace token is held in React memory, not browser storage. The token protects paid calls; the dashboard itself is public. No paid calls were made during development.

The custom tool-calling loop requires `inspect_fit` and `get_project_evidence`, then validates a structured answer. It permits up to three model requests per analysis and does not automatically retry failures. It never sends emails or submits applications. Usage is billed by the model provider only after activation and an authenticated AI analysis request.

The hosted pipeline and profile persist in localStorage on this browser/device, not a hosted database. This is a personal workspace release, not a multi-user SaaS. Project claims are user supplied and require human verification. The website labels illustrative product previews and rule-based outputs.

## Local Python dashboard

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app:app --reload
```

Open http://127.0.0.1:8000. The local app stores records in SQLite. Choose `APPLYPILOT_PROVIDER=rules`, `openai`, or `ollama`. Paid OpenAI mode requires both an API key and the explicit enable flag. Ollama requires a downloaded local model on 127.0.0.1:11434; it does not use cloud fallback.

## Validation status

Free preview and activation guards can be checked without a live model. A real OpenAI or local-model result still requires verification after you provide credentials or install a model. No live job discovery, Gmail integration, resume parsing, or automatic submission is included.
