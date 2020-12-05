#!/bin/bash

dynamodb_path="/devlab/persistent_data/dynamodb/data"
ddb_user=$(getent passwd | grep dynamodb | cut -d ':' -f 1)

if [ -z "$ddb_user" ] ; then
    ddb_user=1000
fi
if [ ! -d "$dynamodb_path" ] ; then
    echo "Dynamodb path: '$dynamodb_path' does not exist, creating"
    mkdir -p "$dynamodb_path"
fi
if [ -z "$ddb_user" ] ; then
    ddb_user=1000
fi
chown -R "$ddb_user" "$dynamodb_path"
