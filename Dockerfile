FROM node:24.17.0-bookworm-slim

ARG CLAUDE_CODE_VERSION=2.1.207
ARG CCR_VERSION=3.0.3

LABEL org.opencontainers.image.title="multi-agent-claude-live-validator" \
      org.opencontainers.image.description="Claude Code and CCR live validator for an existing Ollama endpoint" \
      io.fr407.claude-code.version="${CLAUDE_CODE_VERSION}" \
      io.fr407.claude-code-router.version="${CCR_VERSION}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl jq python3 python3-venv procps iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && npm install --global "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" "@musistudio/claude-code-router@${CCR_VERSION}" \
    && npm cache clean --force

WORKDIR /workspace
COPY config/ccr/config.json /root/.claude-code-router/config.json
COPY scripts/container-entrypoint.sh /usr/local/bin/container-entrypoint
RUN chmod 0755 /usr/local/bin/container-entrypoint

ENV HOME=/root \
    CCR_CONFIG_PATH=/root/.claude-code-router/config.json \
    ANTHROPIC_BASE_URL=http://127.0.0.1:3456 \
    ANTHROPIC_AUTH_TOKEN=local-router-token \
    ANTHROPIC_API_KEY=local-router-token

EXPOSE 3456
HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 \
  CMD curl --fail --silent http://127.0.0.1:3456/health >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/container-entrypoint"]
