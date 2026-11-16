#!/usr/bin/env bash
# Build Harness context hook.
#   session: say where the plugin lives (the init skill needs it) and load the standing principles.
#   prompt:  re-inject the standing principles on every prompt, so they never scroll out of context.
# Prints nothing when the project has no standing principles, so it stays quiet outside harnessed repos.
mode="${1:-prompt}"
project="${CLAUDE_PROJECT_DIR:-$PWD}"
principles="$project/docs/standing-principles.md"

if [ "$mode" = "session" ]; then
  echo "Build Harness plugin root: ${CLAUDE_PLUGIN_ROOT}"
  if [ ! -f "$project/harness/node_converge.py" ]; then
    echo "Build Harness is not installed in this repository. The /build-harness:init skill installs it."
  fi
fi
if [ -f "$principles" ]; then
  echo "STANDING PRINCIPLES (Build Harness; binding on every turn):"
  head -c 8000 "$principles"
fi
exit 0
