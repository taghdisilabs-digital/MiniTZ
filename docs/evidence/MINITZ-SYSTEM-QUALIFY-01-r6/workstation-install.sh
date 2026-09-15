set -eu
mkdir -p /tmp/shims /tmp/bin
printf '#!/bin/sh
test "$*" = daemon-reload
' >/tmp/shims/systemctl
chmod +x /tmp/shims/systemctl
export PATH=/tmp/shims:$PATH
export MINITZ_WORKSTATION_INSTALL_DIR=/tmp/installed
export MINITZ_WORKSTATION_CLI_LINK=/tmp/bin/minitz-workstation
export MINITZ_RESOURCE_CLI_LINK=/tmp/bin/minitz-resource
bash /workspace/repo/ops/workstation/install-minitz-workstation.sh
/tmp/bin/minitz-resource --help
python3 -c 'import sys;sys.path.insert(0,"/tmp/installed");import minitz_local_quality; print("installed_quality_module_import=PASS")'
