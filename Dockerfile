# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install cron
RUN apt-get update && apt-get install -y cron git openssh-client && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data
COPY scripts ./scripts
COPY .env.example .env.example

# Install dependencies
RUN uv sync --frozen --no-dev

# Create volume mount points for persistent data
VOLUME ["/app/data"]

# Set up cron job — runs every 6 hours by default
COPY scripts/crontab /etc/cron.d/autonomous-tw
RUN chmod 0644 /etc/cron.d/autonomous-tw && crontab /etc/cron.d/autonomous-tw

# Copy entrypoint script
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["cron"]