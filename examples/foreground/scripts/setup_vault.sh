#!/bin/sh
###
### Setup needed things for 'my_app'
###

function wait_for_listen {
    local ENDPOINT="$1"
    local ENDPOINT_PORT="$2"
    if nc -vz $ENDPOINT $ENDPOINT_PORT > /dev/null 2>&1 ; then
        return
    fi
    echo "Waiting for ${ENDPOINT} to start listening on: ${ENDPOINT_PORT} "
    local count=0
    while ! nc -vz $ENDPOINT $ENDPOINT_PORT > /dev/null 2>&1; do
        if [ $count -ge 30 ] ; then
            echo "ERROR: still not listening after 30 seconds... giving up"
            exit 1
        fi
        echo 'Still Waiting'
        sleep 1
        let count+=1
    done
    echo
}

vault_ip=$(echo $VAULT_ADDR | grep -o '[^a-zA-Z:/]\+' | head -n 1)
vault_port=$(echo $VAULT_ADDR | grep -o '[^a-zA-Z:/]\+' | tail -n 1)

wait_for_listen $vault_ip $vault_port

if [ -f /devlab/persistent_data/vault/env ] ; then
    source /devlab/persistent_data/vault/env
    echo "Un-sealing vault..."
    unseal_out=$(vault operator unseal $UNSEAL_TOKEN 2>&1)
    rc=$?
    if [ $rc -eq 0 ] ; then
        if echo "$unseal_out" | grep -i '^Sealed' |grep -q false ; then
            exit 0
        fi
    fi
    echo "$unseal_out"
    echo "Failed to Un-seal the vault"
    exit 1
fi
echo "Initializing vault..."
vault operator init -key-shares=1 -key-threshold=1 2>&1 > /devlab/persistent_data/vault/init.out

echo "Parsing unseal and root tokens"
export UNSEAL_TOKEN=$(cat /devlab/persistent_data/vault/init.out | grep '^Unseal Key 1: ' | awk '{print $4}')
export VAULT_TOKEN=$(cat /devlab/persistent_data/vault/init.out | grep '^Initial Root Token: ' | awk '{print $4}')

echo "Writing Env file"
VAULT_IP=$(ip addr | grep 'inet ' | tail -n 1 | awk '{print $2}' | cut -d '/' -f 1)
GEN_VAULT_ADDR=$(echo $VAULT_ADDR | grep -o '[htps]\+' | head -n 1)://${VAULT_IP}:$(echo $VAULT_ADDR | grep -o '[0-9]\+' | tail -n 1)
cat <<EOF > /devlab/persistent_data/vault/env
export UNSEAL_TOKEN='${UNSEAL_TOKEN}'
export VAULT_TOKEN='${VAULT_TOKEN}'
export VAULT_ADDR='${GEN_VAULT_ADDR}'
export VAULT_IP='${VAULT_IP}'
EOF

echo "Unsealing freshly initialized vault"
vault operator unseal $UNSEAL_TOKEN

# Create a new policy for my_app
echo "Creating my_app policy"
vault policy write my_app - <<EOF
path "secret/my_app/*" {
    capabilities = [ "read" ]
}
path "auth/token/lookup-self" {
    capabilities = [ "read" ]
}
path "auth/token/renew-self" {
    capabilities = [ "update" ]
}
EOF

# Create a token for my_app to use with the new policy
echo "Creating token for my_app to use"
vault token create -policy=my_app -no-default-policy -period=336h 2>&1 > /devlab/persistent_data/vault/my_app_token.out
export MY_APP_TOKEN=$(cat /devlab/persistent_data/vault/my_app_token.out | grep '^token ' | awk '{print $2}')

echo "Parsing and storing my_app token into env file"
echo "export MY_APP_TOKEN='${MY_APP_TOKEN}'" >> /devlab/persistent_data/vault/env

#Create a default secret kv store
vault secrets enable -path=secret -description='Generic secrets' kv

echo "Creating some values for secret/my_app/sensitive"
vault kv put secret/my_app/sensitive value='
{
    "sensitive": "Only \"my_app\" should be able to see this!"
}'
