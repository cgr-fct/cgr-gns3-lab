# CGR router/switch ("cgr-frr")
#
# A tiny Linux network node, modelled on Cumulus Linux "classic" mode:
#   * front-panel ports are called swp1, swp2, ... (eth0 = management)
#   * interfaces are configured with ifupdown2 (/etc/network/interfaces, `ifreload -a`)
#     -> ifupdown2 was written by Cumulus Networks; it is the same tool/syntax
#   * routing is FRRouting, configured with `vtysh` (the same CLI Cumulus uses)
#
# Multi-arch: builds for linux/amd64 and linux/arm64 (Apple Silicon).
# Memory footprint at idle: ~40-60 MB.
ARG BASE=debian:bookworm-slim
FROM ${BASE}

# FRR_REPO: "frr-stable" -> latest FRR from deb.frrouting.org (recommended)
#           ""           -> FRR version shipped by the distribution
ARG FRR_REPO=frr-stable
# IFUPDOWN2: package name to install ("" if the base image already has it)
ARG IFUPDOWN2=ifupdown2

ENV DEBIAN_FRONTEND=noninteractive
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release; \
    if [ -n "$FRR_REPO" ]; then \
      curl -fsSL https://deb.frrouting.org/frr/keys.gpg -o /usr/share/keyrings/frrouting.gpg; \
      echo "deb [signed-by=/usr/share/keyrings/frrouting.gpg] https://deb.frrouting.org/frr $(lsb_release -s -c) $FRR_REPO" \
        > /etc/apt/sources.list.d/frr.list; \
      apt-get update; \
    fi; \
    apt-get install -y --no-install-recommends \
      frr frr-pythontools $IFUPDOWN2 iproute2 iputils-ping traceroute \
      tcpdump lldpd openssh-server procps less nano vim-tiny \
      bash-completion sudo; \
    rm -rf /var/lib/apt/lists/*; \
    # No default frr.conf in the image: the entrypoint creates one only if missing,
    # so a config pre-loaded by tools/cgr_lab.py survives GNS3's first-boot copy.
    rm -f /etc/frr/frr.conf; \
    mkdir -p /run/sshd /etc/network/interfaces.d /usr/local/share/cgr; \
    # GNS3 mounts its own (empty) /etc/network: keep a copy of ifupdown2's config
    cp -a /etc/network/ifupdown2 /usr/local/share/cgr/ifupdown2; \
    # Lab login (SSH): cgr / cgr   (the GNS3 console opens a root shell directly)
    useradd -m -s /bin/bash -G frrvty,frr cgr; \
    echo 'cgr:cgr' | chpasswd; \
    echo 'root:cgr' | chpasswd; \
    echo 'cgr ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/cgr; \
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

COPY daemons vtysh.conf /etc/frr/
COPY entrypoint.sh /usr/local/sbin/cgr-entrypoint
COPY motd /etc/motd
RUN chmod 755 /usr/local/sbin/cgr-entrypoint && chown -R frr:frr /etc/frr

LABEL org.opencontainers.image.title="cgr-frr" \
      org.opencontainers.image.description="CGR GNS3 lab router/switch: FRRouting + ifupdown2, swpN ports"

# GNS3 keeps these folders per node (they survive stop/start and project export)
VOLUME ["/etc/frr", "/root"]

CMD ["/usr/local/sbin/cgr-entrypoint"]
