# Single image serving the dashboard + running the Kronos/TradingAgents
# pipeline in-process on a schedule. See render.yaml for how this is deployed.
FROM python:3.12-slim

WORKDIR /app

# System deps for torch / build steps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY kronos-model/requirements.txt kronos-model/requirements.txt
COPY trading-agents/pyproject.toml trading-agents/pyproject.toml
COPY trading-agents/tradingagents trading-agents/tradingagents

RUN pip install --no-cache-dir -r kronos-model/requirements.txt \
    && pip install --no-cache-dir ./trading-agents \
    && pip install --no-cache-dir fastapi "uvicorn[standard]" apscheduler

COPY kronos-model/ kronos-model/
COPY trading-agents/ trading-agents/
COPY dashboard/ dashboard/

# Pre-download Kronos-small weights at build time so the first real request
# isn't stuck waiting on a Hugging Face download.
RUN cd kronos-model && python -c "from forecast import forecast; forecast('AAPL')"

WORKDIR /app/dashboard
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
