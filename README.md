# ApplyPilot

**Current cost policy:** Paid model calls are hard-disabled in code, even if an API key exists. Only local deterministic analysis runs. The SDK integration below is retained for reference and is not active.

An evidence-grounded job-search agent for people who want useful automation without handing over the final decision.

Paste a job listing and ApplyPilot checks your configured constraints, compares the role with your profile, and prepares an editable outreach draft. With an OpenAI API key configured, an **OpenAI Agents SDK** agent calls two bounded tools—deterministic fit inspection and retrieval of user-entered project evidence—then returns a structured summary, risks, next steps, and draft. Every analysis and approval action is recorded in a local SQLite activity history. It never sends email or submits applications.

## Run locally

Requires Python 3.10+.

```bash
cd applypilot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# No API key is needed. Paid model calls are disabled.
uvicorn app:app --reload
```

Open <http://127.0.0.1:8000>. Without an API key, the deterministic eligibility and fit workflow still works. An API key alone cannot enable model calls; the code-level spending block remains active.

## Workflow

1. Add skills, target roles, constraints, and verifiable projects under **My profile**.
2. Paste a job description and its public listing URL.
3. Review deterministic eligibility findings separately from the agent's written analysis.
4. Edit and save the draft, then mark it ready for your own next step.

Duplicate listing URLs update their existing record. Hard constraints (for example, advanced Spanish when the profile says it is not available) are checked in code and cannot be overridden by the agent.

## API

- `GET /health` — service and agent configuration status
- `GET/PUT /api/profile` — profile and evidence
- `POST /api/jobs/analyze` — analyze a job and persist the result
- `GET /api/applications` and `GET /api/applications/{id}` — pipeline
- `PATCH /api/applications/{id}/draft` — save a reviewed draft
- `POST /api/applications/{id}/review` — mark a draft ready or dismiss it
- `GET /api/activity` — audit trail
- `GET /docs` — OpenAPI documentation

## Privacy and deployment

The default database is `applypilot/applypilot.db`; set `APPLYPILOT_DB` to move it. Job descriptions and profile evidence stay in that SQLite database. When the model is enabled, the submitted job description and non-project profile fields are sent to the configured OpenAI model; project evidence is returned to the agent through its bounded tool. Keep `.env` and the database out of source control.

This first release is designed for one user's local workspace. It has no login, multi-user isolation, hosted database, or production deployment hardening. Do not expose it publicly until authentication, HTTPS, encrypted storage, abuse controls, and deployment secrets are configured.
