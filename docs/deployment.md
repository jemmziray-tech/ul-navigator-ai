# Deployment notes

The public app uses a Next.js frontend on Vercel and a FastAPI backend on Google Cloud Run. Configure frontend `BACKEND_URL` for the same-origin `/backend` proxy and `NEXT_PUBLIC_API_URL=/backend`. Review `frontend/next.config.ts` for the proxy configuration.

For local containers, copy `.env.example` to `.env`, set your own values, and run `docker compose -f deploy/docker-compose.yml up --build`. Populate the backend index through ingestion. The generic Render blueprint is an alternative example; review provider requirements and costs before using it.

Provision your own secrets, persistent storage and allowed origins. Production account IDs, resource names, private deployment logs, state replicas and credentials are intentionally excluded. Never upload local chat databases as deployment seeds.

SQLite and local vector storage require a single writer. Multiple instances need a suitable shared-storage design. Before a replacement deployment, preserve persistent state and verify backups and restore behavior. Set your own usage limits and monitoring; do not assume a budget alert is a hard spending limit.
