<div align="center">

# 🛡️ DeepGuard AI
### Multi-Agent Deepfake Video Forensics Assistant

Google ADK • Gemini • MCP • Agent Skills • FastAPI • React • Docker

Production-ready AI Agent System built for the Kaggle × Google
5-Day AI Agents Intensive Capstone.

---

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Google ADK](https://img.shields.io/badge/Google-ADK-orange)
![Gemini](https://img.shields.io/badge/Gemini-API-blueviolet)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688)
![React](https://img.shields.io/badge/React-Frontend-61DAFB)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

# Overview

DeepGuard AI is a production-style **multi-agent AI system** that assists users in investigating whether a video contains signs of manipulation.

Instead of relying on a single chatbot, DeepGuard coordinates multiple specialized AI agents that inspect uploaded videos, analyze metadata, organize forensic evidence, generate investigation reports, and recommend further verification steps.

The project demonstrates modern **Agent Engineering** concepts taught during the Google × Kaggle AI Agents Intensive.

---

# Features

✅ Multi-Agent Architecture (Google ADK)

✅ Workflow Orchestration

✅ Agent Skills

✅ MCP Integration

✅ Metadata Analysis

✅ Explainable AI Reports

✅ Upload Validation

✅ Secure File Handling

✅ Deployment Ready

---

# Architecture

```text
                              User
                                │
                                ▼
                       React Frontend
                                │
                                ▼
                         FastAPI Backend
                                │
                                ▼
                  Google ADK Coordinator Agent
                                │
      ┌───────────────┬───────────────┬───────────────┐
      ▼               ▼               ▼               ▼

 Video Agent    Evidence Agent   Report Agent   Recommendation Agent

      │               │               │               │
      └───────────────┴───────────────┴───────────────┘
                                │
                                ▼
                          MCP Server Layer
                   • Filesystem
                   • Image Processing
                   • PDF Generation

                                │
                                ▼
                           Agent Skills
                 • Video Validation
                 • Metadata Reader
                 • Evidence Summary
                 • Report Writer
                 • Recommendation Generator

                                │
                                ▼
                         Structured Response
```

---

# Workflow

```text
User Uploads Video
        │
        ▼
Upload Validation
        │
        ▼
Coordinator Agent
        │
        ├────────────► Video Inspection Agent
        │                    │
        │                    ▼
        │             Extract Metadata
        │
        ├────────────► Evidence Agent
        │                    │
        │                    ▼
        │          Analyze Forensic Indicators
        │
        ├────────────► Report Agent
        │                    │
        │                    ▼
        │          Generate Investigation Report
        │
        └────────────► Recommendation Agent
                             │
                             ▼
               Suggest Additional Verification
                             │
                             ▼
                    Final Response to User
```

---

# Technology Stack

## Frontend

- React
- TypeScript
- Vite
- TailwindCSS

---

## Backend

- Python
- Google ADK
- FastAPI
- Gemini API
- Hugging Face APIs

---

## Agent Engineering

- Multi-Agent Workflow
- Google ADK
- Agent Skills
- MCP Server
- Prompt Engineering

---

## Deployment

- Docker
- FastAPI
- Cloud Run Ready

---

# Project Structure

```text
DeepGuard-AI/

├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
├── backend/
│   ├── agents/
│   ├── workflows/
│   ├── skills/
│   ├── mcp/
│   ├── tools/
│   ├── utils/
│   ├── config/
│   ├── tests/
│   └── app/
│
├── README.md
├── .gitignore
└── LICENSE
```

---

# Kaggle Concepts Demonstrated

| Concept | Status |
|---------|--------|
| Google ADK | ✅ |
| Multi-Agent Workflow | ✅ |
| Agent Skills | ✅ |
| MCP Server | ✅ |
| Security | ✅ |
| Deployability | ✅ |

---

# Security

- Upload Validation
- Allowed File Types
- File Size Limits
- Prompt Injection Protection
- Safe Report Generation
- Structured Error Handling

---

# Future Enhancements

- Local Deepfake Detection Models
- Face Manipulation Localization
- Temporal Consistency Analysis
- Explainable Heatmaps
- Video Timeline Viewer
- Cloud Deployment
- Authentication
- Database Integration

---

# Getting Started

## Clone

```bash
git clone https://github.com/yourusername/DeepGuard-AI.git

cd DeepGuard-AI
```

---

## Frontend

```bash
cd frontend

npm install

npm run dev
```

---

## Backend

```bash
cd backend

pip install -r requirements.txt

adk web
```

---

# Built For

Google × Kaggle

5-Day AI Agents Intensive Capstone

2026

---

# License

MIT License

---

<div align="center">

### ⭐ If you found this project interesting, consider giving it a Star.

</div>