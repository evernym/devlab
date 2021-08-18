#!/bin/bash

if [ "${CI_COMMIT_TAG:0:1}" == "v" ] ; then
    export VERSION=${CI_COMMIT_TAG:1}
fi

for asset in $(find artifacts/ -type f) ; do
    fname=$(basename $asset)
    echo "Uploading asset: $asset"
    curl --header "JOB-TOKEN: ${CI_JOB_TOKEN}" --upload-file $asset ${PACKAGE_REGISTRY_URL}/${VERSION}/${fname} || exit 1
    echo "Looking up package id"
    page=1
    while [ ! -z "$page" ] ; do
        echo "Checking for package id on page: ${page}"
        pkg_id=$(curl -sf ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages?page=${page} | jq ".[] | select(.version==\"${VERSION}\") | select(.name==\"devlab\") | select(.package_type==\"generic\") | .id")
        if [ $? -ne 0 ] ; then
            echo "Failed querying repo's packages at: ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages?page=${page}"
            exit 1
        fi
        if [ ! -z "$pkg_id" ] ; then
            echo "Found pkg_id: $pkg_id"
            break
        fi
        curl_headers=$(curl -sfI ${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages?page=${page})
        page=$(echo "$curl_headers" | grep -i '^x-next-page' | grep -o '[0-9]\+')
    done
    if [ -z "$pkg_id" ] ; then
        echo "Failed looking up package id"
        echo "$pkg_id"
        exit 1
    fi
    echo "Looking up file inside package"
    pkg_file_id=$(curl -sf "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/packages/${pkg_id}/package_files" | jq ".[] | select(.file_name==\"${fname}\") | .id") || exit 1
    if [ -z "$pkg_file_id" ] ; then
        echo "Failed looking up package file id"
        echo "$pkg_file_id"
        exit 1
    fi
    echo "Generating the direct download link"
    direct_dl="${CI_PROJECT_URL}/-/package_files/${pkg_file_id}/download"
    echo "$fname|${direct_dl}" >> ./artifacts/assets.out
done
