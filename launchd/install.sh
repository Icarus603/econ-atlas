#!/bin/zsh
set -euo pipefail

usage() {
  cat <<'EOF'
Install econ-atlas launchd agents (macOS).

Usage:
  ./launchd/install.sh [--port 8765] [--no-crawl]

What it does:
  - Generates two plists under ~/Library/LaunchAgents/
    - com.icarus603.econatlas.viewer.plist (always-on local viewer)
    - com.icarus603.econatlas.crawl.plist (weekly crawl + viewer build) unless --no-crawl
  - Bootstraps + enables the jobs, and starts the viewer immediately.

Notes:
  - The generated plists are local-only and should NOT be committed.
EOF
}

port=8765
enable_crawl=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      port="${2:-}"
      shift 2
      ;;
    --no-crawl)
      enable_crawl=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${port}" ]]; then
  echo "Missing --port value" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
uid="$(id -u)"
home="${HOME}"
logs_dir="${home}/Library/Logs"
launch_agents_dir="${home}/Library/LaunchAgents"

mkdir -p "${logs_dir}" "${launch_agents_dir}"

uv_path="$(command -v uv || true)"
if [[ -z "${uv_path}" ]]; then
  echo "uv not found in PATH. Install uv first." >&2
  exit 1
fi

render() {
  local template="$1"
  local output="$2"
  sed -e "s#__UV_PATH__#${uv_path}#g" \
      -e "s#__REPO_ROOT__#${repo_root}#g" \
      -e "s#__HOME__#${home}#g" \
      -e "s#__PORT__#${port}#g" \
      "${template}" > "${output}"
}

viewer_tpl="${repo_root}/launchd/com.icarus603.econatlas.viewer.plist.template"
crawl_tpl="${repo_root}/launchd/com.icarus603.econatlas.crawl.plist.template"

viewer_plist="${launch_agents_dir}/com.icarus603.econatlas.viewer.plist"
crawl_plist="${launch_agents_dir}/com.icarus603.econatlas.crawl.plist"

render "${viewer_tpl}" "${viewer_plist}"
if [[ "${enable_crawl}" -eq 1 ]]; then
  render "${crawl_tpl}" "${crawl_plist}"
fi

# If an older version is already loaded, boot it out first so changes take effect.
launchctl bootout "gui/${uid}" "${viewer_plist}" 2>/dev/null || true
launchctl enable "gui/${uid}/com.icarus603.econatlas.viewer" 2>/dev/null || true
launchctl bootstrap "gui/${uid}" "${viewer_plist}" 2>/dev/null || true
launchctl kickstart -k "gui/${uid}/com.icarus603.econatlas.viewer" 2>/dev/null || true

if [[ "${enable_crawl}" -eq 1 ]]; then
  launchctl bootout "gui/${uid}" "${crawl_plist}" 2>/dev/null || true
  launchctl bootstrap "gui/${uid}" "${crawl_plist}" 2>/dev/null || true
  launchctl enable "gui/${uid}/com.icarus603.econatlas.crawl" 2>/dev/null || true
fi

echo "Installed."
echo "Viewer: http://127.0.0.1:${port}/viewer/"
echo "Logs: ${logs_dir}/econatlas-*.log"
