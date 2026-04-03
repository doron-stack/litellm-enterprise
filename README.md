# LiteLLM Enterprise Setup — Redis Cache + Full Monitoring

Zero manual file editing. One-click Docker setup optimized for AI swarm token savings.

## Quick Start (Windows + Docker Desktop)

### Option 1: PowerShell one-liner
```powershell
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/doron-stack/litellm-enterprise/main/setup.ps1" -OutFile "$env:TEMP\setup-litellm.ps1" -UseBasicParsing; & "$env:TEMP\setup-litellm.ps1"
```

### Option 2: Manual
```
git clone https://github.com/doron-stack/litellm-enterprise.git
cd litellm-enterprise
docker compose up -d --pull always
```

## Login Details

| Service | URL | Username | Password |
|---------|-----|----------|----------|
| LiteLLM Admin UI | http://localhost:4000/ui | admin | admin123 |
| Prometheus | http://localhost:9090 | — | — |
| Grafana | http://localhost:3100 | admin | adminchangeinproduction |

## Add LLM Models
1. Open http://localhost:4000/ui
2. Log in → Models → Add Model
3. Enter model name, provider, API key → Save

## Architecture
- **LiteLLM Proxy** — unified API gateway for all LLM providers
- **Redis** — response caching (saves tokens on repeated queries)
- **PostgreSQL** — persistent storage for keys, models, usage logs
- **Prometheus** — metrics collection (cache hits/misses, latency, tokens)
- **Grafana** — dashboards and alerting
