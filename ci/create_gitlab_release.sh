#!/bin/sh

if [ "${CI_COMMIT_TAG:0:1}" == "v" ] ; then
    export VERSION=${CI_COMMIT_TAG:1}
fi

ASSET_ARGS=''
echo "Locating custom assets:"
for asset in $(cat ./artifacts/assets.out) ; do
    fname=$(echo "$asset" | cut -d '|' -f 1)
    url=$(echo "$asset" | cut -d '|' -f 2)
    echo "Found asset: $fname at url: $url"
    ASSET_ARGS="$ASSET_ARGS --assets-link {\"name\":\"${fname}\",\"url\":\"${url}\"}"
done

echo "Creating gitlab release with the following asset arguments:"
echo "asset arguments: $ASSET_ARGS"

release-cli create --name "New Version ${VERSION}" --description "artifacts/new_changes.md" --tag-name "$CI_COMMIT_TAG" $ASSET_ARGS
