#!/bin/bash

source /devlab/persistent_data/vault-example/env

echo "Type 'exit' to exit"
while read -p 'Press "Enter" to display my_app secret: ' line; do
    if [ "$line" == 'exit' ] ; then
        echo "Exiting"
        break
    fi
    echo "Displaying sensitive information from vault"
    RES=$(curl -Ss -X GET -H "X-Vault-Token: $MY_APP_TOKEN" ${VAULT_ADDR}/v1/secret/my_app/sensitive 2>&1)
    rc=$?
    if [ $rc -ne 0 ] ;then
        echo "$RES"
        echo "Failed getting sensitive info from vault"
        exit 1
    fi
    echo "$RES" | python -m json.tool
done
