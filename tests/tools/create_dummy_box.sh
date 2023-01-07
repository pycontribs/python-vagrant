#!/bin/bash
set -euo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
PROVIDER="$1"
TMPDIR="$(mktemp -d)"

if [ $# -ne 1 ]; then
	echo "Missing provider" >&2
	exit 1
fi

if [ -f "${DIR}/dummy-${PROVIDER}.box" ]; then
	echo "Box already created"
	exit 0
fi

cd "${TMPDIR}" || exit 1
echo "{ \"provider\": \"${PROVIDER}\"}" > metadata.json
tar czf "${DIR}/dummy-${PROVIDER}.box" .
cd "${DIR}" || exit 1
rm -rvf "${TMPDIR}"
