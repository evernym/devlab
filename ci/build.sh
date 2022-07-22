#!/bin/bash
dev_release=true
proj_root=$(realpath "$0")
proj_root=$(dirname "$proj_root")
proj_root=$(dirname "$proj_root")
cd "$proj_root"
last_change=$(git rev-parse HEAD)
tags=$(git tag -l 'v[0-9]*' | sort -rV)
last_release_tag=$(echo "$tags" | head -n 1)
prev_release_tag=$(echo "$tags" | sed -n 2p)
version_files=( './devlab' )
if [ ! -z "$last_release_tag" ] ; then
    beg_range="${last_release_tag}.."
else
    beg_range=''
fi
changes_since_release=''
release_ver=''

#Check to see if this is tagged release (Non-dev)
if [ ! -z "$CI_COMMIT_TAG" ] ; then
    #CI_COMMIT_TAG variable is set, running from a gitlab pipeline triggered
    #from a tag
    dev_release=false
    release_ver="${CI_COMMIT_TAG:1}"
    last_change=$last_release_tag
    beg_range="${prev_release_tag}.."
else
    #check for fallback logic of special commit names etc...
    legacy_changes=$(git log --pretty=format:'%s%n' | sed "/^Merge branch '.\+' into '.\+'/d ; /^Merge branch '.\+' of .\+/d ; /^\$/d")
    legacy_last_change=$(echo "$legacy_changes" | head -n 1)
    legacy_last_release=$(echo "$legacy_changes" | grep -m 1 '^New release: ')
    if [ "$legacy_last_change" == "$legacy_last_release" ] ; then
        dev_release=false
        release_ver=$(echo "$legacy_last_release" | cut -d ' ' -f 3)
    fi
fi
echo "Getting commit changes between: ${beg_range}${last_change}"
changes_since_release=$(git log --pretty=format:'%s%n' ${beg_range}${last_change} | sed "/^Merge branch '.\+' into '.\+'/d ; /^Merge branch '.\+' of .\+/d; /^$/d")

if [ $(echo "$changes_since_release" | wc -l) -gt 0 ] ; then
    echo -e "Building a package with the following NEW changes included:\n----"
    echo "$changes_since_release" | nl -s '. '
    echo -e '----\n'
fi

release_ver=${release_ver:-${last_release_tag:1}}
#If this is not a new release, then create a new development build
if [ "$dev_release" == true ] ; then
    release_ver="${release_ver:-0.0.0}+$(date +%s)dev"
    echo "Making a development build: $release_ver"
else
    echo "Building new release candidate: $release_ver"
fi

mkdir -p artifacts
if [ -d 'build/' ]; then
    rm -rf 'build/'
fi
mkdir -p build/devlab

#Copy in the module
cp -r devlab_bench/ build/devlab/
#Cleanup any byte code
find build/devlab/devlab_bench -type f -name '*.pyc' -exec rm '{}' \;
pcache_dirs=$(find build/devlab/devlab_bench -type d -name '__pycache__')
for pcache in $pcache_dirs ; do
    rm -rf "$pcache"
done
#Copy in the executable
cp devlab build/devlab/
cp installer.py build/devlab/
chmod a+rx build/devlab/devlab
chmod a+rx build/devlab/installer.py
#Copy in docker files
cp -r docker build/devlab/

#Update version in files
for file in "${version_files[@]}"; do
    echo "Updating version string in: build/devlab/${file}"
    perl -p -i -e "s/^(__VERSION__\\s*=\\s*).+$/\${1}'${release_ver}'/g" "build/devlab/${file}"
    perl -p -i -e "s/^(__version__\\s*=\\s*).+$/\${1}'${release_ver}'/g" "build/devlab/${file}"
    perl -p -i -e "s/^(\\s+\"version\":\\s*\")\\d+\\.\\d+\\.\\d+(\",\\s*)\$/\${1}${release_ver}\${2}/" "build/devlab/${file}"
    perl -p -i -e "s/^(\\s+\"VERSION\":\\s*\")\\d+\\.\\d+\\.\\d+(\",\\s*)\$/\${1}${release_ver}\${2}/" "build/devlab/${file}"
done

if [ -f "./setup.py" ] ; then
    #Update setup.py
    echo "Updating setup.py"
    perl -p -i -e "s/(version=).+\$/\${1}'${release_ver}',/"  "./setup.py"
fi
#Package it all up
tar cvz -C build/ devlab > artifacts/devlab_${release_ver}_all.tgz
echo "$changes_since_release" > artifacts/new_changes.log

echo "Generating a summary of the build's recent changes in markdown from: artifacts/new_changes.log"
echo -e "# Changes\n$(cat artifacts/new_changes.log | sed 's/^/ * /')" > artifacts/new_changes.md
