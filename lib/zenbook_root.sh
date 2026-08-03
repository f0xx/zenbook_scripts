# shellcheck shell=bash
# Resolve zenbook-scripts install root (repo checkout or /usr/share, /usr/local/share).
zenbook_share_dir() {
    local here src candidate

    src="${BASH_SOURCE[1]:-${BASH_SOURCE[0]}}"
    here="$(cd "$(dirname "${src}")" && pwd)"
    if [[ -f "${here}/../zenbook_kb/hotkey.py" || -f "${here}/../lib/protocol.sh" ]]; then
        echo "$(cd "${here}/.." && pwd)"
        return 0
    fi
    for candidate in /usr/share/zenbook-scripts /usr/local/share/zenbook-scripts; do
        if [[ -f "${candidate}/zenbook_kb/hotkey.py" || -f "${candidate}/lib/protocol.sh" ]]; then
            echo "${candidate}"
            return 0
        fi
    done
    echo "zenbook-scripts share dir not found (tried repo, /usr/share, /usr/local/share)" >&2
    return 1
}
