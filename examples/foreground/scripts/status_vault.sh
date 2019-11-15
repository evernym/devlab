#!/bin/sh
bridge_ip=$(ip addr | grep 'inet ' | grep -v 'host lo' | awk '{print $2}' | cut -d '/' -f 1 | head -n 1)
source /devlab/persistent_data/vault/env

function gen_status {
    local rc
    local vault_status
    local health
    vault_status=$(VAULT_ADDR=http://127.0.0.1:8200 vault status 2>&1)
    rc=$?
    health="healthy"
    if [ $rc -ne 0 ] ; then
        echo "$vault_status" >&2
        echo "Failed getting status of vault. Aborting!" >&2
        health="degraded(bad status)"
    fi
    cat <<EOF
{
    "status": {
        "health": "$health"
    },
    "links": [
        {
            "link": "${VAULT_ADDR}",
            "comment": "Vault address endpoint"
        },
        {
            "link": "",
            "comment": "  - App token: ${MY_APP_TOKEN}"
        }
    ]
}
EOF
    return $rc
}

gen_status
