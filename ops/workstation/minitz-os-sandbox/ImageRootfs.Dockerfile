FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive
RUN printf '#!/bin/sh\nexit 101\n' >/usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d && \
    apt-get update && apt-get install -y --no-install-recommends \
    systemd-sysv linux-image-generic initramfs-tools python3 ca-certificates \
    grub-efi-amd64-bin grub-common dosfstools mtools e2fsprogs gdisk \
    coreutils && \
    rm -f /usr/sbin/policy-rc.d && rm -rf /var/lib/apt/lists/*
COPY source/ /opt/minitz/source/
COPY source.json /etc/minitz/source.json
RUN printf '#!/bin/sh\nexport MINITZ_SOURCE_ROOT=/opt/minitz/source\nexport MINITZ_SOURCE_MANIFEST=/etc/minitz/source.json\nexport PYTHONPATH=/opt/minitz/source/src${PYTHONPATH:+:$PYTHONPATH}\nexec python3 -m minitz_os "$@"\n' >/usr/bin/minitz && chmod 0755 /usr/bin/minitz && \
    mkdir -p /usr/local/libexec && \
    cp /opt/minitz/source/ops/workstation/minitz-os-sandbox/minitz-boot-proof.sh /usr/local/libexec/minitz-boot-proof && chmod 0755 /usr/local/libexec/minitz-boot-proof && \
    cp /opt/minitz/source/ops/workstation/minitz-os-sandbox/minitz-boot-proof.service /etc/systemd/system/minitz-boot-proof.service && \
    mkdir -p /etc/systemd/system/multi-user.target.wants && \
    ln -sf ../minitz-boot-proof.service /etc/systemd/system/multi-user.target.wants/minitz-boot-proof.service && \
    printf 'LABEL=MINITZROOT / ext4 defaults 0 1\n' >/etc/fstab && \
    printf 'minitz-os\n' >/etc/hostname && truncate -s 0 /etc/machine-id
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
