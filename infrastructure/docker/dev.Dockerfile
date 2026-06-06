FROM mcr.microsoft.com/devcontainers/python:3.12-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

USER root

# Base dev packages (small layer — caches well)
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        jq \
        postgresql-client \
        unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Node 20 (matches frontend.Dockerfile)
RUN export DEBIAN_FRONTEND=noninteractive \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# AWS CLI v2 (separate layer — large download, fails independently if corrupt)
RUN curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip

RUN git config --system --add safe.directory '*'

WORKDIR /workspaces/Propel

USER vscode

CMD ["sleep", "infinity"]
