#!/bin/bash
set -euxo pipefail

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

if [ $# -ne 1 ]; then
	echo "Missing provider" >&2
	exit 1
fi

if [ -f "$DIR/dummy.box" ]; then
	echo "Box already created"
	exit 0
fi

PROVIDER="$1"
TMPDIR=`mktemp -d`
cd "$TMPDIR"
echo "{ \"provider\": \"$PROVIDER\"}" > metadata.json
tar czf "$DIR/dummy-$PROVIDER.box" .
cd "$DIR"
rm -rf "$TMPDIR"
