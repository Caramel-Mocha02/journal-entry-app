# Deployment guidance

## Recommended direction

This project is a Python + Streamlit app for local-first accounting review and journal suggestion. For this kind of app, the most practical path is:

1. GitHub for version control and collaboration.
2. Streamlit Community Cloud, Render, Railway, or a small VPS for deployment.
3. Keep OCR, SQLite, and local AI features local unless a production environment is explicitly prepared.

## Why Vercel is not the first choice

Vercel is a strong fit for frontend apps and Node-based deployments, but not the best default for this project because:

- it is primarily optimized for web frontends,
- the app is Python-based,
- OCR and local AI execution do not fit well with a serverless-first frontend host,
- the app is designed to stay local-first and review-oriented.

## Recommended release flow

### Phase 1: local-first MVP

- GitHub repository set up
- requirements locked
- tests passing
- local launch confirmed

### Phase 2: shared internal deployment

- deploy on Streamlit Community Cloud or Render
- keep SQLite local or move to a managed DB only when needed
- add secret/env configuration for Ollama host if remote AI is introduced

### Phase 3: production hardening

- add auth and access control
- move storage to a managed database if multiple users access the same instance
- add logging, backups, and audit retention policies
- review whether AI inference should remain local-only

## Suggested environment variables

```bash
STREAMLIT_SERVER_HEADLESS=true
STREAMLIT_SERVER_PORT=8501
OLLAMA_BASE_URL=http://localhost:11434
```

## Next action to publish

- create the GitHub repository
- push the current codebase
- choose a deployment target that supports Python apps
- set a limited environment for internal review before public release
