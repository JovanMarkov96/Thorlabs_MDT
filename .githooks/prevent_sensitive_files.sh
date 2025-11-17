#!/bin/sh
# Prevent committing forbidden local files
forbidden='^\\.mdt_dlls/|^mdt_devices\\.json$|^mdt_probe\\.json$'
staged=$(git diff --cached --name-only)
echo "$staged" | grep -E "$forbidden" >/dev/null 2>&1
if [ $? -eq 0 ]; then
  echo "ERROR: Commit contains forbidden local files:" >&2
  echo "$staged" | grep -E "$forbidden" >&2
  echo "These files should remain local only. To remove them from the index run:" >&2
  echo "  git rm --cached <file>" >&2
  exit 1
fi
exit 0
