FROM python:3.11-slim

# Node.js 20 for Claude Code CLI
RUN apt-get update && apt-get install -y curl ffmpeg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm install -g @anthropic-ai/claude-code && \
    rm -rf /var/lib/apt/lists/*

# Claude Code CLI refuses --dangerously-skip-permissions when running as root
RUN useradd -m -u 1000 lumys

WORKDIR /app

# Install Python deps
COPY orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy orchestrator code
COPY orchestrator/ ./orchestrator/

# Copy all agent runners and CLAUDE.md files
COPY agents/ ./agents/

# Claude Code skills (systematic-debugging, mcp-builder, cold-email)
COPY .claude/ ./.claude/

RUN chown -R lumys:lumys /app

# Both /app (for agents.*) and /app/orchestrator (for router, sessions, voice)
ENV PYTHONPATH=/app:/app/orchestrator

USER lumys

CMD ["python", "-u", "orchestrator/bot.py"]
