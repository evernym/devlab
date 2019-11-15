#!/bin/bash

OWNER=${GITHUB_OWNER:-evernym}
REPO=${GITHUB_REPO:-devlab}
USER=${GITHUB_USERNAME:-evernym-ci}
PASS="$GITHUB_PASSWORD"
RELEASE_ID=''
TOKEN="$GITHUB_PERSONAL_ACCESS_TOKEN"
CURL_OPTS="${CURL_OPTS:--Ss}"
CURL_CONFIG=""

REAL_CURL_OPTS=()
VERSION="${1:-$CI_COMMIT_TAG}"
RELEASE_BODY="$2"

function add_curl_opt {
    REAL_CURL_OPTS=( "${REAL_CURL_OPTS[@]}" "$@" )
}

#This is a hacky way of using eval to process the args in CURL_OPTS to preserve
#argument position even with spaces inside quotes etc...
eval 'for word in '$CURL_OPTS'; do add_curl_opt "$word"; done'

if [ -z "$TOKEN" ] ; then
    if [ -z "$PASS" ] ; then
        read -sp "Enter password for user '$USER': " PASS
    fi
    CURL_CONFIG="user = ${USER}:${PASS}"
else
    add_curl_opt -H "Authorization: token ${TOKEN}"
fi

if [ -z "$VERSION" ] ; then
    echo "No version was supplied as the first arg! Aborting!"
    exit 1
fi

if [ "${VERSION:0:1}" == "v" ] ; then
    VERSION="${VERSION:1}"
fi

if [ -z "$RELEASE_BODY" ] ; then
    if [ -f "artifacts/new_changes.log" ] ; then
        echo "Loading most recent changes from: artifacts/new_changes.log"
        RELEASE_BODY=$(cat artifacts/new_changes.log)
    fi
fi

if [ ! -z "$RELEASE_BODY" ] ; then
    RELEASE_BODY=$(echo "$RELEASE_BODY" | sed 's/^/ * /')
    RELEASE_BODY=$(echo -e "# Changes\n$RELEASE_BODY" | sed 's/$/\\n/g' | tr -d '\n')
fi

RELEASE_JSON=$(cat <<EOF
{
  "tag_name": "v${VERSION}",
  "target_commitish": "master",
  "name": "New Version ${VERSION}",
  "body": "$RELEASE_BODY",
  "draft": false,
  "prerelease": false
}
EOF
)

echo -e "\n===RELEASE_JSON==="
echo "$RELEASE_JSON"
echo "===END==="

release_resp=$(curl -K <(cat <<<"$CURL_CONFIG") "${REAL_CURL_OPTS[@]}" -X POST https://api.github.com/repos/${OWNER}/${REPO}/releases -d "$RELEASE_JSON")
rel_rc=$?
if [ $rel_rc -ne 0 ] ; then
    echo "$release_resp"
    exit $rel_rc
fi
RELEASE_ID=$(echo "$release_resp" | jq '.id' 2>&1)
echo "New release id is: $RELEASE_ID"
if [ "$RELEASE_ID" == 'null' -o -z "$RELEASE_ID" ] ; then
    echo "Curl Command: 'curl "${REAL_CURL_OPTS[@]}" -X POST https://api.github.com/repos/${OWNER}/${REPO}/releases -d '$RELEASE_JSON'"
    echo "Failed to parse the release id from key 'id' in output:"
    echo "$release_resp"
    exit 1
fi

for asset in $(find artifacts/ -type f) ; do 
    echo "=== Uploading: $asset ==="
    # deb: application/vnd.debian.binary-package
    # tar.gz: application/gzip
    # text: text/plain
    fname=$(basename $asset)
    ctype=$(file -b --mime-type $asset)
    up_resp=$(curl -K <(cat <<<"$CURL_CONFIG") "${REAL_CURL_OPTS[@]}" -H "Content-Type: ${ctype}" --data-binary "@${asset}" https://uploads.github.com/repos/${OWNER}/${REPO}/releases/${RELEASE_ID}/assets?name=${fname} 2>&1)
    up_rc=$?
    echo "$up_resp" | python3 -m json.tool
    if [ $up_rc -ne 0 ] ; then
        echo "$up_resp"
        exit $up_rc
    fi
done
