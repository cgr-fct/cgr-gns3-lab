# CGR router/switch ("cgr-frr")
#
# A small Linux network node, modelled on Cumulus Linux "classic" mode:
#   * front-panel ports are called swp1, swp2, ... (eth0 = management)
#   * interfaces are configured with ifupdown2 (/etc/network/interfaces, `ifreload -a`)
#     -> ifupdown2 was written by Cumulus Networks; it is the same tool/syntax
#   * routing is FRRouting, configured with `vtysh` (the same CLI Cumulus uses)
#   * DHCP server and relay: ISC dhcpd / dhcrelay
#   * a RESTCONF server (HTTPS, port 443) for the cgr-device YANG model
#
# Multi-arch: builds for linux/amd64 and linux/arm64 (Apple Silicon).
# Build context must be the REPOSITORY ROOT:
#   docker build -f images/frr/Dockerfile -t cgr-frr .
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
      isc-dhcp-server isc-dhcp-relay \
      python3 python3-jinja2 python3-yaml python3-pip openssl \
      tcpdump lldpd openssh-server procps less nano vim-tiny \
      bash-completion sudo; \
    rm -rf /var/lib/apt/lists/*; \
    # No default frr.conf in the image: the entrypoint creates one only if missing,
    # so a config pre-loaded by tools/cgr_lab.py survives GNS3's first-boot copy.
    rm -f /etc/frr/frr.conf; \
    mkdir -p /run/sshd /etc/network/interfaces.d /usr/local/share/cgr /etc/cgr; \
    # GNS3 mounts its own (empty) /etc/network: keep a copy of ifupdown2's config
    cp -a /etc/network/ifupdown2 /usr/local/share/cgr/ifupdown2; \
    # DHCP daemons are started by the entrypoint only when configured
    printf 'INTERFACESv4=""\nINTERFACESv6=""\n' > /etc/default/isc-dhcp-server; \
    printf 'SERVERS=""\nINTERFACES=""\nOPTIONS=""\n' > /etc/default/isc-dhcp-relay; \
    # Lab login (SSH): cgr / cgrlab   (the GNS3 console opens a root shell directly)
    useradd -m -s /bin/bash -G frrvty,frr cgr; \
    echo 'cgr:cgrlab' | chpasswd; \
    echo 'root:cgrlab' | chpasswd; \
    echo 'cgr ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/cgr; \
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config

# yangson validates configuration against the YANG model (RESTCONF server)
ARG EXTRA_PIP="yangson"
RUN if [ -n "$EXTRA_PIP" ]; then pip3 install --no-cache-dir --break-system-packages $EXTRA_PIP; fi

COPY images/frr/daemons images/frr/vtysh.conf /etc/frr/
COPY images/frr/entrypoint.sh /usr/local/sbin/cgr-entrypoint
COPY images/frr/motd /etc/motd
COPY automation /usr/local/lib/cgr
RUN chmod 755 /usr/local/sbin/cgr-entrypoint /usr/local/lib/cgr/*.py \
 && chown -R frr:frr /etc/frr \
 && ln -s /usr/local/lib/cgr/restconf_server.py /usr/local/sbin/cgr-restconf \
 && rm -rf /usr/local/lib/cgr/backups /usr/local/lib/cgr/reports /usr/local/lib/cgr/__pycache__

LABEL org.opencontainers.image.title="cgr-frr" \
      org.opencontainers.image.description="CGR GNS3 lab router/switch: FRRouting, ifupdown2, ISC DHCP, RESTCONF"

# GNS3 keeps these folders per node (they survive stop/start and project export)
VOLUME ["/etc/frr", "/etc/dhcp", "/etc/default", "/etc/cgr", "/root"]

CMD ["/usr/local/sbin/cgr-entrypoint"]
