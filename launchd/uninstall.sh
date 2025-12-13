#!/bin/zsh
set -euo pipefail

uid="$(id -u)"
home="${HOME}"
launch_agents_dir="${home}/Library/LaunchAgents"

viewer_plist="${launch_agents_dir}/com.icarus603.econatlas.viewer.plist"
crawl_plist="${launch_agents_dir}/com.icarus603.econatlas.crawl.plist"

launchctl bootout "gui/${uid}" "${viewer_plist}" 2>/dev/null || true
launchctl bootout "gui/${uid}" "${crawl_plist}" 2>/dev/null || true

rm -f "${viewer_plist}" "${crawl_plist}"
echo "Uninstalled."

