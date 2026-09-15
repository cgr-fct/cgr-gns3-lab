# CGR automation station ("cgr-netauto")
# The "network engineer's laptop" inside the lab: it sits on the management
# network and can reach every device's NVUE REST API (Cumulus) and SSH.
#
# Includes: Python 3 + requests, PyYAML, Jinja2, jsonschema, paramiko/netmiko,
#           ansible-core, curl, jq, ssh, git, nano/vim.
# The repo's automation/ folder is copied to /root/cgr (persistent in GNS3).
# Build context must be the REPOSITORY ROOT:
#   docker build -f images/netauto/Dockerfile -t cgr-netauto .
ARG BASE=debian:bookworm-slim
FROM ${BASE}

ENV DEBIAN_FRONTEND=noninteractive
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      python3 python3-requests python3-yaml python3-jinja2 python3-jsonschema \
      python3-paramiko python3-venv python3-pip \
      curl jq openssh-client sshpass iputils-ping iproute2 traceroute \
      git nano vim-tiny less bash-completion ca-certificates; \
    rm -rf /var/lib/apt/lists/*

ARG EXTRA_PIP="ansible-core netmiko"
RUN if [ -n "$EXTRA_PIP" ]; then pip3 install --no-cache-dir --break-system-packages $EXTRA_PIP; fi

COPY automation /root/cgr
COPY images/netauto/motd /etc/motd
RUN chmod +x /root/cgr/*.py /root/cgr/*.sh 2>/dev/null || true; \
    printf '%s\n' 'cat /etc/motd' 'cd /root/cgr' 'export PYTHONDONTWRITEBYTECODE=1' >> /root/.bashrc

LABEL org.opencontainers.image.title="cgr-netauto" \
      org.opencontainers.image.description="CGR GNS3 lab automation station (Python, YAML, Jinja2, REST)"

VOLUME ["/root"]
WORKDIR /root/cgr
CMD ["/bin/bash", "--login"]
