#!/bin/bash
# CGR router/switch start-up. GNS3 has already created eth0..ethN and run its own
# (busybox) ifup before we get here.
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

log() { echo "[cgr] $*"; }

# 1. Rename data ports eth1..ethN -> swp1..swpN (eth0 stays as management)
for path in /sys/class/net/eth*; do
  dev=${path##*/}
  [[ $dev =~ ^eth[0-9]+$ ]] || continue
  n=${dev#eth}
  [ "$n" = "0" ] && continue
  ip link set dev "$dev" down 2>/dev/null
  ip link set dev "$dev" name "swp$n" 2>/dev/null && log "$dev -> swp$n"
  ip link set dev "swp$n" up 2>/dev/null
done

# 2. Kernel settings for a router/switch
sysctl -qw net.ipv4.ip_forward=1 net.ipv6.conf.all.forwarding=1 2>/dev/null
sysctl -qw net.ipv4.conf.all.rp_filter=0 net.ipv4.conf.default.rp_filter=0 2>/dev/null

# 3. Default interfaces file (GNS3 normally writes one; keep it if present)
if [ ! -s /etc/network/interfaces ]; then
  cat > /etc/network/interfaces <<'EOF'
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
EOF
fi
mkdir -p /etc/network/interfaces.d /run/network
# GNS3 mounts its own /etc/network volume, which hides ifupdown2's config dir
[ -f /etc/network/ifupdown2/ifupdown2.conf ] || cp -a /usr/local/share/cgr/ifupdown2 /etc/network/

# 4. Apply interface config with ifupdown2 (Cumulus-style syntax)
if ! ifreload -a >/tmp/ifreload.log 2>&1; then
  log "ifreload reported problems (see /tmp/ifreload.log)"
fi

# 5. FRR
if [ ! -s /etc/frr/frr.conf ]; then
  printf 'frr defaults datacenter\nhostname %s\nlog syslog informational\nservice integrated-vtysh-config\n!\nend\n' "$(hostname)" > /etc/frr/frr.conf
fi
chown -R frr:frr /etc/frr
chmod 640 /etc/frr/frr.conf
/usr/lib/frr/frrinit.sh start >/tmp/frr-start.log 2>&1 || log "FRR failed to start (see /tmp/frr-start.log)"

# 6. Helpers
service lldpd start >/dev/null 2>&1 || lldpd >/dev/null 2>&1
/usr/sbin/sshd >/dev/null 2>&1 || true

cat /etc/motd
cd /root || true
# Keep a shell on the GNS3 console forever (typing `exit` just opens a new one)
while true; do
  /bin/bash --login
done
