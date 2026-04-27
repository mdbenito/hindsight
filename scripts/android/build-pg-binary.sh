#!/bin/bash
# Build a portable PostgreSQL + pgvector binary for Android ARM64.
#
# This extracts the PG binaries from the Termux package repository and
# packages them as a tar.gz that can be bundled in the APK assets.
#
# The resulting archive contains:
#   bin/   - postgres, initdb, createdb, psql, pg_isready, pg_ctl
#   lib/   - shared libraries (libpq, pgvector, etc.)
#   share/ - PostgreSQL data files (timezone, SQL scripts, etc.)
#
# Usage:
#   bash scripts/android/build-pg-binary.sh
#   # Output: dist/android-arm64/postgres-arm64.tar.gz
#
# Prerequisites: Docker (uses ARM64 Termux container)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$REPO_ROOT/dist/android-arm64"
OUTPUT_FILE="$OUTPUT_DIR/postgres-arm64.tar.gz"
mkdir -p "$OUTPUT_DIR"

echo "=== Building PostgreSQL ARM64 binary for Android ==="

# Use Docker with ARM64 platform to extract Termux packages
# This gives us PG binaries compiled against Android's Bionic libc
docker run --rm --platform linux/arm64 \
    -v "$OUTPUT_DIR:/output" \
    ubuntu:24.04 bash -c '
set -e

apt-get update -qq && apt-get install -y -qq curl tar xz-utils > /dev/null 2>&1

# Download Termux packages directly from the repo
TERMUX_REPO="https://packages-cf.termux.dev/apt/termux-main"
ARCH="aarch64"

mkdir -p /pg-build/bin /pg-build/lib /pg-build/share

# Download PostgreSQL package
echo "Downloading PostgreSQL..."
PG_PKG=$(curl -s "$TERMUX_REPO/dists/stable/main/binary-$ARCH/Packages" | \
    grep -A1 "^Package: postgresql$" | grep "Filename:" | awk "{print \$2}")
curl -sL "$TERMUX_REPO/$PG_PKG" -o /tmp/postgresql.deb
dpkg-deb -x /tmp/postgresql.deb /tmp/pg-extract

# Copy binaries
cp /tmp/pg-extract/data/data/com.termux/files/usr/bin/postgres /pg-build/bin/
cp /tmp/pg-extract/data/data/com.termux/files/usr/bin/initdb /pg-build/bin/
cp /tmp/pg-extract/data/data/com.termux/files/usr/bin/createdb /pg-build/bin/
cp /tmp/pg-extract/data/data/com.termux/files/usr/bin/psql /pg-build/bin/
cp /tmp/pg-extract/data/data/com.termux/files/usr/bin/pg_isready /pg-build/bin/
cp /tmp/pg-extract/data/data/com.termux/files/usr/bin/pg_ctl /pg-build/bin/
cp /tmp/pg-extract/data/data/com.termux/files/usr/bin/pg_config /pg-build/bin/

# Copy libraries
cp -a /tmp/pg-extract/data/data/com.termux/files/usr/lib/libpq.* /pg-build/lib/ 2>/dev/null || true
cp -a /tmp/pg-extract/data/data/com.termux/files/usr/lib/postgresql/ /pg-build/lib/postgresql/ 2>/dev/null || true

# Copy share data (timezones, SQL scripts, extensions)
cp -a /tmp/pg-extract/data/data/com.termux/files/usr/share/postgresql/ /pg-build/share/postgresql/ 2>/dev/null || true

# Download dependent libraries we need
for dep in libicu libxml2 libcrypt libuuid libandroid-shmem libandroid-posix-semaphore; do
    DEP_PKG=$(curl -s "$TERMUX_REPO/dists/stable/main/binary-$ARCH/Packages" | \
        grep -A1 "^Package: $dep$" | grep "Filename:" | awk "{print \$2}" | head -1)
    if [ -n "$DEP_PKG" ]; then
        echo "  Downloading $dep..."
        curl -sL "$TERMUX_REPO/$DEP_PKG" -o /tmp/$dep.deb
        dpkg-deb -x /tmp/$dep.deb /tmp/$dep-extract
        cp -a /tmp/$dep-extract/data/data/com.termux/files/usr/lib/*.so* /pg-build/lib/ 2>/dev/null || true
    fi
done

echo "Building archive..."
cd /pg-build
tar czf /output/postgres-arm64.tar.gz bin/ lib/ share/
echo "Done! Files:"
ls -lh /output/postgres-arm64.tar.gz
echo "Contents:"
tar tzf /output/postgres-arm64.tar.gz | head -20
echo "..."
'

echo ""
echo "=== PostgreSQL binary built ==="
ls -lh "$OUTPUT_FILE"
echo ""
echo "To use in APK:"
echo "  cp $OUTPUT_FILE hindsight-android-sdk/app/src/main/assets/"
