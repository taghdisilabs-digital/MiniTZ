#!/usr/bin/env bash
set -Eeuo pipefail
# Installer compilers only; never mutate project source or execution state.
[[ "$EUID" -eq 0 ]] || { printf 'Run as root to add installer tools.\n' >&2; exit 1; }
command -v apt-get >/dev/null || { printf 'This installer targets Debian/Ubuntu hosts.\n' >&2; exit 1; }
missing=()
for package in dpkg nsis nsis-common; do
  state="$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)"
  [[ "$state" == 'install ok installed' ]] || missing+=("$package")
done
if (( ${#missing[@]} )); then
  DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l apt-get install --no-install-recommends -y "${missing[@]}"
fi
command -v dpkg-deb
makensis -VERSION
