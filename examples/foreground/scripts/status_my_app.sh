#!/bin/bash
bridge_ip=$(ip addr | grep 'inet ' | grep -v 'host lo' | awk '{print $2}' | cut -d '/' -f 1 | head -n 1)
source /devlab/persistent_data/vault/env

function gen_status {
    local rc
    local can_reach_vault
    local health
    can_reach_vault=$(curl -Ss -X GET -H "X-Vault-Token: $MY_APP_TOKEN" ${VAULT_ADDR}/v1/secret/my_app/sensitive 2>&1)
    health="healthy"
    rc=$?
    if [ $rc -ne 0 ] ;then
        echo "$can_reach_vault"
        echo "Failed getting sensitive info from vault" >&2
        health="degraded(vlt fail)"
    fi
    cat <<EOF
{
    "status": {
        "health": "$health"
    },
    "links": []
}
EOF
    return $rc
}

gen_status
