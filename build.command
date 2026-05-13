#!/usr/bin/env bash
# Build macOS executable Beatfinder desktop. Double-clic depuis Finder, ou
# ./build.command en CLI. Équivalent de build.sh pour macOS.
#
# Pré-requis identiques (voir build.sh).

set -euo pipefail
cd "$(dirname "$0")"
exec ./build.sh
