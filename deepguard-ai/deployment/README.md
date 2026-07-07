# DeepGuard AI — Deployment Guide

This project is production-ready for both local and cloud deployment.

## Option 1: Local Docker Compose (Recommended)

The easiest way to run the full stack (Frontend, Backend, MCP Server) is via Docker Compose.

1. Copy `.env.example` to `.env` and add your `GOOGLE_API_KEY`:
   ```bash
   cp .env.example .env
   ```
2. Start the stack:
   ```bash
   docker-compose up --build
   ```
3. Services will be available at:
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - MCP Server: Port 8090

## Option 2: Cloud Run (Google Cloud)

To deploy the backend to Google Cloud Run:

1. Build and push the container image to Google Container Registry (GCR) or Artifact Registry.
2. Deploy the image to Cloud Run, exposing port 8000.
3. Set the `GOOGLE_API_KEY` environment variable in the Cloud Run configuration.

## Option 3: Terraform (Google Cloud)

Infrastructure-as-Code templates are provided in the `deployment/terraform` directory for deploying the agent to Vertex AI Agent Engine.

See `deployment/terraform/README.md` for more details.
