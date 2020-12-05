#!/bin/bash

args=$#
args_left=$args
dynamodb_path="/var/lib/dynamodb"
endpoint='localhost'
endpoint_port='8000'
sam_template='/devlab/template.yaml'
set_empty=false
set_provision=false
set_list_tables=false
set_create_tables=false
set_delete_tables=false
status_output=false

function get_table_defs_from_sam {
    if [ ! -f "$1" ] ; then
        echo "ERROR: SAM template at: '$1' NOT found!"
        return 1
    fi
    python <<EOF
import yaml
import json

class SafeLoaderIgnoreUnknown(yaml.SafeLoader):
    def ignore_unknown(self, node):
        return None

class FindInMapLoader(SafeLoaderIgnoreUnknown):
    def list_map(self, keys):
        v = None
        for k in keys:
            if v:
                v = v[k]
            else:
                v = self.mappings[k]
        return v
    def map_lookup(self, node):
        value = self.construct_sequence(node)
        resolved = self.list_map(value)
        return resolved

SafeLoaderIgnoreUnknown.add_constructor(None, SafeLoaderIgnoreUnknown.ignore_unknown)

FindInMapLoader.add_constructor('!FindInMap', FindInMapLoader.map_lookup)
FindInMapLoader.add_constructor(None, FindInMapLoader.ignore_unknown)

with open('/devlab/template.yaml') as tfile:
    template_str = tfile.read()

pre_template = yaml.load(template_str, Loader=SafeLoaderIgnoreUnknown)
FindInMapLoader.mappings = pre_template['Mappings']

template = yaml.load(template_str, Loader=FindInMapLoader)

for key in template['Resources']:
    if template['Resources'][key]['Type'] == 'AWS::DynamoDB::Table':
        print(json.dumps(template['Resources'][key]['Properties']))
EOF
}

function gen_status {
    local current_tables
    current_tables=( $(list_tables) )
    local ct_rc=$?
    health="healthy"
    if [ $ct_rc -ne 0 ] ; then
        echo "Failed querying current tables from dynamodb Aborting!" >&2
        health="degraded"
    elif [ ! -z "$current_tables" ] ; then
        for t in "${tables[@]}"; do
            tab_exists=false
            for cur_tab in "${current_tables[@]}" ; do
                if echo "$t" | grep -q "\"$cur_tab\"" ; then
                    tab_exists=true
                    break
                fi
            done
            if [ $tab_exists != "true" ] ; then
                echo "Table: '$cur_tab' is missing!" >&2
                health="degraded"
            fi
        done
    else
        echo "No tables found..." >&2
        health="degraded"
    fi
    cat <<EOF
{
    "status": {
        "health": "$health"
    },
    "links": [
        {
            "link": "http://{host_ip}:{local_port}",
            "comment": ""
        }
    ]
}
EOF
}

function install_prereqs {
    DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends -y default-jre curl
}

function install_dynamodb {
    if [ ! -f ${dynamodb_path}/DynamoDBLocal.jar ] ; then
        adduser --system --home ${dynamodb_path} --shell /bin/bash dynamodb
        cd "${dynamodb_path}"
        curl -Ss -L http://dynamodb-local.s3-website-us-west-2.amazonaws.com/dynamodb_local_latest.tar.gz | tar xz
        tar_rc=$?
        cd -
        if [ $tar_rc -ne 0 ] ; then
            echo "ERROR: Was not able to successfully extract dynamodb local application"
            exit 1
        fi
    else
        #Make sure that dynamodb_path is owned by dynamodb user
        ddb_user=$(getent passwd | grep dynamodb | cut -d ':' -f 1)
        if [ ! -d "$dynamodb_path" ] ; then
            mkdir -p "$dynamodb_path"
        fi
        chown "$ddb_user" "$dynamodb_path"
    fi
}

function setup_service {
    #Create a dynamodb service file
    if [ ! -f /etc/systemd/system/dynamodb.service ] ; then
        cat <<-EOF > /etc/systemd/system/dynamodb.service
    [Unit]
    Description=Local Dynamodb
    Requires=network.target

    [Service]
    User=dynamodb
    WorkingDirectory=${dynamodb_path}
    Environment="JAVA_OPTS="
    ExecStart=/usr/bin/java -Djava.library.path=./ -jar ./DynamoDBLocal.jar -sharedDb

    [Install]
    WantedBy=multi-user.target
EOF
        systemctl daemon-reload
        systemctl enable dynamodb
    else
        echo "SystemD service script already exists, Skipping"
    fi

    if ! systemctl is-active -q dynamodb ; then
        echo "Starting dynamodb service"
        systemctl start dynamodb
    else
        echo "Dynamodb service already running"
    fi
    wait_for_up
}
function wait_for_up {
    echo "Waiting for dynamodb service to start"
    count=0
    while ! curl -sq $endpoint:$endpoint_port > /dev/null 2>&1; do
        if [ $count -ge 5 ] ; then
            echo "ERROR: dynamodb service is still not listening after 5 seconds... giving up"
            exit 1
        fi
        echo 'Still waiting'
        sleep 1
        let count+=1
    done
}

function list_tables {
    current_tables=$(
        curl -Ss -X POST \
            -H "Host: ${endpoint}:${endpoint_port}" \
            -H "Accept-Encoding: identity" \
            -H "Content-Type: application/x-amz-json-1.0" \
            -H 'Authorization: AWS4-HMAC-SHA256 Credential=cUniqueSessionID/20171230/us-west-2/dynamodb/aws4_request, Signature=42e8556bbc7adc659af8255c66ace0641d9bce213fb788f419c07833169e2af8' \
            -H "X-Amz-Target: DynamoDB_20120810.ListTables" \
            "http://${endpoint}:${endpoint_port}/" \
            -d '{}' | grep -o '\[.*\]' | grep -o '[a-z_-]*'
    )
    curl_rc=$?
    message=$(echo "$current_tables" | grep message)
    if [ $curl_rc -ne 0 -o ! -z "$message" ] ; then
        echo "Failed looking up current list of tables" >&2
        if [ ! -z "$message" ] ; then
            resp_msg="$message"
        elif [ ! -z "$current_tables" ] ; then
            resp_msg="$current_tables"
        else
            resp_msg="Curl request returned: $curl_rc"
        fi
        echo "Response: $resp_msg" >&2
        return 100
    fi
    echo "${current_tables}"
}
function create_tables {
    echo -e "\nQuerying current list of tables.."
    local current_tables
    current_tables=( $(list_tables) )
    ct_rc=$?
    if [ $ct_rc -ne 0 ] ; then
        echo "Aborting!"
        return 1
    fi
    echo "Looking up table definitions from SAM template: $sam_template"
    tables=( $(get_table_defs_from_sam "$sam_template" | sed 's/ /%20/g') )
    if echo "${tables[@]}" | grep -q ERROR ; then
        echo "${tables[@]}" | sed 's/%20/ /g'
        echo "Aborting"
        return 1
    fi
    echo -e "Creating tables"
    for t in "${tables[@]}"; do
        t=$(echo "$t" | sed 's/%20/ /g' | python3 -m json.tool)
        tname=$(echo "$t" | grep 'TableName' | cut -d ':' -f 2 | tr -d '", ')
        skip=false
        for cur_tab in "${current_tables[@]}" ; do
            if [ "$tname" == "$cur_tab" ] ; then
                echo "Table: '$cur_tab' already exists, skipping..."
                skip=true
                break
            fi
        done
        if [ "$skip" == true ] ; then
            continue
        fi
        echo "Creating table: '$tname'"
        curl_out=$(curl -Ss "http://${endpoint}:${endpoint_port}/" \
            -H "Host: ${endpoint}:${endpoint_port}" \
            -H 'Content-Type: application/x-amz-json-1.0' \
            -H 'X-Amz-Target: DynamoDB_20120810.CreateTable' \
            -H 'Authorization: AWS4-HMAC-SHA256 Credential=cUniqueSessionID/20171230/us-west-2/dynamodb/aws4_request, Signature=42e8556bbc7adc659af8255c66ace0641d9bce213fb788f419c07833169e2af8' \
            -H 'Connection: keep-alive' \
            --compressed \
            --data "$t")
        curl_rc=$?
        message=$(echo "$curl_out" | grep message)
        if [ $curl_rc -ne 0 -o ! -z "$message" ] ; then
            echo "Failed creating table with definition"
            echo "$t"
            echo -e '\n\nResponse:'
            echo "$curl_out"
            echo "Aborting!"
            break
        fi
        sleep 0.5
    done
}

function delete_tables {
    local tables="${1//,/ }"
    local current_tables
    local deleted
    echo -e "Querying current list of tables.."
    current_tables=( $(list_tables) )
    ct_rc=$?
    if [ $ct_rc -ne 0 ] ; then
        echo "Aborting!"
        return 1
    fi
    if [ -z "$tables" ] ; then
        tables=( "${current_tables[@]}" )
    else
        tables=( $tables )
    fi
    for t in "${tables[@]}"; do
        deleted=false
        for cur_tab in "${current_tables[@]}" ; do
            if [ "$t" == "$cur_tab" ] ; then
                echo -e "Deleting table: '$t'"
                curl_out=$(curl -Ss "http://${endpoint}:${endpoint_port}/" \
                    -H "Host: ${endpoint}:${endpoint_port}" \
                    -H 'Content-Type: application/x-amz-json-1.0' \
                    -H 'X-Amz-Target: DynamoDB_20120810.DeleteTable' \
                    -H 'Authorization: AWS4-HMAC-SHA256 Credential=cUniqueSessionID/20171230/us-west-2/dynamodb/aws4_request, Signature=42e8556bbc7adc659af8255c66ace0641d9bce213fb788f419c07833169e2af8' \
                    -H 'Connection: keep-alive' \
                    --compressed \
                    --data "{\"TableName\":\"$t\"}")
                curl_rc=$?
                message=$(echo "$curl_out" | grep message)
                if [ $curl_rc -ne 0 -o ! -z "$message" ] ; then
                    echo "Failed deleteing table"
                    echo "$t"
                    echo -e '\n\nResponse:'
                    echo "$curl_out"
                    echo "Aborting!"
                    return 1
                fi
                deleted=true
                break
            fi
        done
        if [ "$deleted" == false ] ; then
            echo "Table: '$t' doesn't exist... Skipped"
        fi
    done
}

function empty_db {
    delete_tables
    create_tables
}

function provision_dynamodb {
    install_prereqs
    install_dynamodb
    setup_service
    create_tables
    exit $?
}

function help {
    cat <<EOF
Usage: $(basename $0) <action>

ACTIONS:
    --create-tables
                Create cas/eas/vas tables
    --delete-tables <tables>
                Delete the table(s) <table>. Comma separated for multiple
    --empty     Empty delete the dynamodb tables, and recreate them
    --endpoint <host>
        Connect to <host> for setting up tables etc...Default=localhost
    --endpoint-port <port>
        Connect to <port> on the host for setting up tables etc.. Default=8000
    --list-tables
                List all current tables
    --provision Download, install, and set up dynamodb tables locally
    --status    Display a status check for the dynamodb table in json format
    --help      Display this help and exit
EOF
}

while [ $args_left -ge 1 ] ; do
    case "$1" in
        #Actions
        --help|-h)
            help
            exit 0
            ;;
        --empty)
            set_empty=true
            ;;
        --provision)
            set_provision=true
            ;;
        --create-tables)
            set_create_tables=true
            ;;
        --delete-tables)
            if [ ! -z "$2" ] ; then
                set_delete_table=true
                delete_table="$2"
                shift
                let args_left=args_left-1
            else
                echo "Missing parameter argument for '$1'"
                exit 1
            fi
            ;;
        --endpoint)
            if [ ! -z "$2" ] ; then
                endpoint="$2"
                shift
                let args_left=args_left-1
            else
                echo "Missing parameter argument for '$1'"
                exit 1
            fi
            ;;
        --endpoint-port)
            if [ ! -z "$2" ] ; then
                endpoint_port="$2"
                shift
                let args_left=args_left-1
            else
                echo "Missing parameter argument for '$1'"
                exit 1
            fi
            ;;
        --sam-template)
            if [ ! -z "$2" ] ; then
                sam_template="$2"
                shift
                let args_left=args_left-1
            else
                echo "Missing parameter argument for '$1'"
                exit 1
            fi
            ;;
        --status)
            status_output=true
            ;;
        --list-tables)
            set_list_tables=true
            ;;
        *)
            echo "Unknown option: $1"
            help
            exit 1
    esac
    shift
    let args_left=args_left-1
done

if [ "$status_output" == true ] ; then
    gen_status
elif [ "$set_empty" == true ] ; then
    empty_db
elif [ "$set_list_tables" == true ] ; then
    list_tables
elif [ "$set_provision" == true ] ; then
    provision_dynamodb
elif [ "$set_create_tables" == true ] ; then
    wait_for_up
    create_tables
elif [ "$set_delete_table" == true ] ; then
    delete_tables "$delete_table"
else
    echo "No action was specified, aborting!"
    exit 1
fi
