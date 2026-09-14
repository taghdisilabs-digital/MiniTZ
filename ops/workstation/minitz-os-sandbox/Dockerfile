FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 python3-pip python3-venv jq ripgrep curl xz-utils zstd \
    build-essential pkg-config file procps pciutils util-linux rsync sudo && \
    rm -rf /var/lib/apt/lists/*
RUN mkdir -p /workspace /output /state /host-vps /minitz-live /minitz-context /minitz-local-ai
WORKDIR /workspace
CMD ["bash"]
