#!/bin/sh
# Run the benchmarks from any directory, with a local Python fallback if needed.
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

supported_python() {
    "$1" -I -c 'import sys; sys.exit(sys.version_info < (3, 11, 9))' >/dev/null 2>&1
}

python=
if [ "${PYTHON+x}" = x ]; then
    # PYTHON is one executable, not a command with flags. Resolve relative paths
    # before changing directory so caller-provided virtual environments work.
    case "$PYTHON" in
        /*) python=$PYTHON ;;
        */*) python=$PWD/$PYTHON ;;
        *) python=$(command -v "$PYTHON" || true) ;;
    esac
    if [ -z "$python" ] || ! supported_python "$python"; then
        printf '%s\n' 'PYTHON must name a working Python 3.11.9 or newer executable.' >&2
        exit 1
    fi
else
    for candidate in python3 python3.14 python3.13 python3.12 python3.11; do
        executable=$(command -v "$candidate" || true)
        if [ -n "$executable" ] && supported_python "$executable"; then
            python=$executable
            break
        fi
    done
fi

if [ -z "$python" ]; then
    # Official https://github.com/astral-sh/python-build-standalone/releases/tag/20260901
    # Asset digests are pinned here; no executable installer is fetched or run.
    python_version=3.12.14
    python_release=20260901
    case "$(uname -s)-$(uname -m)" in
        Darwin-arm64)
            target=aarch64-apple-darwin
            sha256=81a359f1cfadd4da11766534c5913791cea55f26e1bb902cacd2a531bb1e4b2b
            ;;
        Linux-x86_64)
            target=x86_64-unknown-linux-gnu
            sha256=72748da13197c1fb161e3afeef20a6a385ff24f2165e6e2758e47008e7faba4c
            ;;
        *)
            printf '%s\n' 'Automatic Python setup supports macOS arm64 and Linux x86_64. Install Python 3.11.9+ and set PYTHON to its executable.' >&2
            exit 1
            ;;
    esac
    python_root=$repo_root/.tools-python
    installation=$python_root/cpython-$python_version-$python_release-$target
    python=$installation/python/bin/python3
    if ! supported_python "$python"; then
        if [ -e "$installation" ]; then
            printf 'Incomplete Python installation at %s. Remove that generated directory and retry.\n' "$installation" >&2
            exit 1
        fi
        for dependency in curl tar; do
            if ! command -v "$dependency" >/dev/null 2>&1; then
                printf 'Python bootstrap requires %s. Install Python 3.11.9+ or that utility and retry.\n' "$dependency" >&2
                exit 1
            fi
        done
        if command -v sha256sum >/dev/null 2>&1; then
            checksum=sha256sum
        elif command -v shasum >/dev/null 2>&1; then
            checksum=shasum
        else
            printf '%s\n' 'Python bootstrap requires sha256sum or shasum to verify the download.' >&2
            exit 1
        fi
        mkdir -p "$python_root"
        staging=$(mktemp -d "$python_root/.install.XXXXXXXX")
        trap 'rm -rf "$staging"' EXIT
        trap 'exit 1' HUP INT TERM
        archive=$staging/python.tar.gz
        asset=cpython-$python_version%2B$python_release-$target-install_only_stripped.tar.gz
        printf 'Installing Python %s locally (first run only)...\n' "$python_version"
        curl --fail --location --retry 3 --connect-timeout 30 \
            --output "$archive" \
            "https://github.com/astral-sh/python-build-standalone/releases/download/$python_release/$asset"
        if [ "$checksum" = sha256sum ]; then
            actual=$(sha256sum < "$archive")
        else
            actual=$(shasum -a 256 < "$archive")
        fi
        actual=${actual%% *}
        if [ "$actual" != "$sha256" ]; then
            printf '%s\n' 'Python download checksum mismatch; refusing to extract or execute it.' >&2
            exit 1
        fi
        tar -xzf "$archive" -C "$staging"
        rm "$archive"
        if ! supported_python "$staging/python/bin/python3"; then
            printf '%s\n' 'The downloaded Python could not run on this system.' >&2
            exit 1
        fi
        mv "$staging" "$installation"
        trap - EXIT HUP INT TERM
    fi
fi

# PATH entries can also be relative to the caller.
case "$python" in
    /*) ;;
    *) python=$PWD/$python ;;
esac

cd "$repo_root"
exec "$python" -m benchmarks run --setup "$@"
