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

## Local Autopilot — apply from a job link

The Python dashboard now opens on Autopilot. Save your application identity, relocation and notice-period answers, work authorization, and any reusable Q&A. Set your experience, skills, and target roles under My profile. Upload multiple resumes and cover letters with descriptions of the roles each suits. PDF, DOCX, and TXT text is extracted locally so the planner can use the evidence and select files.

Update and install the browser on your Mac:

```bash
git pull --ff-only
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
APPLYPILOT_PROVIDER=ollama APPLYPILOT_LOCAL_MODEL=qwen3:4b-instruct APPLYPILOT_ENABLE_PAID_API=false uvicorn app:app --reload
```

Paste only the job URL in Autopilot. A visible, dedicated Chromium session reads the listing, checks fit against your saved experience and interests, and fills standard native form controls. Unsuitable or insufficiently described listings are skipped. Login, CAPTCHA, missing answers, and custom controls pause the run for input in that browser. Click Continue in the dashboard after finishing the requested step.

Automatic submission is an explicit saved setting, off initially. When enabled, a known final submission button can be clicked once after required native controls are valid and the planner has no unknown questions. Ambiguous confirmation is recorded as confirmation-needed. Previously attempted submission URLs are blocked from automatic reattempts. The browser remains open for review until you click Continue.

For suitable roles, a LinkedIn first-degree people search opens in the same dedicated browser. Sign in there when prompted. The agent reads visible search results and only retains outreach candidates with a quoted first-degree marker and company evidence. Messages are drafted in the dashboard; there is no send-message action. Search evidence can be incomplete or stale, so review employer and connection details.

Uploads, extracted text, application answers, run logs, and the dedicated browser session live in ignored `private_data/`. Treat this directory as personal data. Run only on your own machine. This feature uses the configured local Ollama model and Playwright; the Vercel dashboard does not launch browsers on your Mac.

Support is currently for visible standard HTML form controls. Custom ATS widgets, popups/new tabs, embedded forms, and site-specific application flows may require manual handoff. End-to-end model/browser application behavior must be verified on your machine before relying on automatic submission. No real job application or LinkedIn message was sent while implementing this feature.
