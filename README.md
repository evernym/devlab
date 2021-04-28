# Purpose
The purpose of the project is to have an easy way to quickly test changes by bringing a stack of components up/down and or resetting to a known state.

You can think of Devlab like a mixture between docker-compose and Vagrant, with orchestration and easy to reset magic sprinkled on top.

It provides:
1. A declarative syntax for components
1. Orchestration features for configuring components as well as determining the order they should be brought up or taken down
1. Built in docker images, as well as runtime images that are part of a project
1. Optional call out to a `wizard` command for generating a config for `devlab` and any files needed for bringing components up

# Installation

There are three options for installing devlab:

1. Clone this repository and execute `./installer.py`
1. Run a one-liner that will extract the installer from the devlab package and execute it:
   * `curl -Ls https://gitlab.com/evernym/utilities/devlab/-/package_files/7923976/download | tar xOvz devlab/installer.py | python`
1. Clone this repository and link it directly to someplace in your path
   * NOTE - This will disable the 'update' feature in devlab and the installer. Meaning you will be using `git` to manage your own updates, which is useful if you are doing development work on `devlab`

# Contributing

If you would like contribute to this project, please do the following:

1. Fork from our gitlab [here](https://gitlab.com/evernym/utilities/devlab)
1. Force a pipeline run (So that you have the needed docker image in your fork's docker registry). This can be done by going to CI/CD -> Pipelines -> Then the button "Run Pipeline"
1. Make changes to your fork. (Best practice is usually to create a branch in your fork, for your changes)
1. Submit an MR to our repo. This can be done by going to Merge Requests -> Click on "New merge request" -> select your fork's branch as the source -> select our target branch (usually master, unless told otherwise)

# Devlab's terms

1. **Project**: A directory with at least a [DevlabConfig.json or DevlabConfig.yaml](#devlab-configuration) that tells devlab how to stand things up
1. **Component**: A container that corresponds to a running service. For example: A component called 'loadbalancer' might have a running `haproxy` service running inside of it
1. **Persistence**: A location that devlab expects a component to store persistent data
1. **Base Image**: An image that is included with, and managed by devlab
1. **Runtime Image**: An image that is defined by, and managed by a project that uses devlab
1. **Script Runner**: An internal reference to a string that can define a script/command to run including where (inside a new container, or an existing component). See [Script Runner Syntax](#script-runner-syntax) for more information.
1. **Provision**: The act of setting up or completing the setup of a component through the use of scripts. See `pre_scripts` and `scripts` in [Component Config Structure](#component-config-structure)
1. **Wizard**: A script that is run before the `up` action. After the wizard has been executed a proper [DevlabConfig.json or DevlabConfig.yaml](#devlab-configuration) should exist. It is normal for the wizard to result in more files than just a `DevlabConfig.json` or `DevlabConfig.yaml`, and those files can be added to the config so that devlab can reset the wizard (forcing it to run again) if so desired.

# Usage
All actions have a `--help` which should display relevent help. The following options below are "global" options and *should* preceed any action:

```
  -h, --help            show this help message and exit
  --log-level, -l {debug,info,warning,error,critical,notset}
                        Set the log-level output
```

The format of the command should be:
`devlab <global options> <action> <action options>`

The "wizard" logic will be invoked the first time you run a `devlab up` command. This can be invoked separately with `wizard` if you so desire.

You can jump right in with a project by going into the directory and running (Examples are in this repository under the `examples` directory): `devlab up`

If you need to reset everything back to normal just: `devlab reset --full`

*[NOTE]* This will also remove the files defined `paths.reset_full` (See [Paths Config Structure](#paths-config-structure))

If you just want to reset a single component: `devlab reset <component>`

If you want to reset a component so that a wizard may notice (depends on whatever wizard your project is using) and possibly force the wizard to run again for it: `devlab reset <component> --reset-wizard`

If you want to reset the devab's configuration: `devlab reset devlab`

## How does it do its thing?
1. The first thing that happens is devlab looks to see if the action set, will need a configuration or not.
1. If an action needs a configuration then devlab will look for a DevlabConfig.json or DevlabConfig.yaml in the current directory, and works its way backward up the filesystem's tree until it finds one... if none is found then it will look for one in the project's root inside of a `defaults/` directory. This way if a wizard is needed other devlab actions can still operate.
1. The `up` action for `devlab` looks for a file in the project's root called `wizard` and executes it if found.
1. The `wizard` should create any needed files, as well as a 'DevlabConfig.json' or 'DevlabConfig.yaml' which indicates how to stand up each component and where paths are that are managed. See [Devlab Configuration](#devlab-configuration) for more information
1. The `wizard` can prompt for values to update in files etc..
1. `devlab` then reads in its configuration from either DevlabConfig.json or DevlabConfig.yaml and continues

# Devlab Configuration
The main configuration file that Devlab uses is a file named `DevlabConfig.json` or `DevlabConfig.yaml`. It defines things like:
1. Which docker network to attach containers to
1. Which components/containers to startup
1. The order to start up containers
1. How to build images that configured components point to
1. Various scripts to run for setting things up
1. Domain name to assign to each component
1. List of components that would need to be reprovisioned if the underlying hosts' IP changes
1. Which files/directories to remove when performing a [reset](#reset-action) action

## YAML support
Although `devlab` support its configuration to be in yaml format (`DevlabConfig.yaml`) this is highly dependent on the `yaml` python module being present on your system. If you would like your project to be more cross platform compatible stick to JSON, otherwise ensure that users of your project know that they'll need to install `yaml` ie:
```
pip install pyyaml
# or if using python3
pip3 install pyyaml
```

## Base Structure
The configuration file has the following base structure:
```
{
    "components": {},
    "domain": "",
    "foreground_component": {},
    "network": {},
    "paths": {},
    "project_filter": "",
    "reprovisionable_components": [],
    "runtime_images": {},
    "wizard_enabled": true
}
```

All Keys that are in **bold** are required to be in the config

| Key | Type  | Value Description |
| --- |  ---  | ---               |
| domain | String | The domain name to assign to all component's hostname inside the container |
| **components** | Hash of Hashes | Defines the components to start up. The First level key is a string of the name of the container. Structure conforms to the [Component Config Structure](#component-config-structure) |
| foreground_component | Hash | Defines a component that will be startup up after ***all*** other components and will run in the foreground. After the process exits, all ther components will be stopped. Same structure as [Component Config Structure](#component-config-structure) with one additional key `name` to indicate the name of the foreground component |
| network | Hash | Defines a docker network to create and/or attach components to. Structure conforms to [Network Config Structure](#network-config-structure) |
| **paths** | Hash | Defines the persistence directory for components, as well as files that should be deleted during the [reset](#reset-action) action. Structure conforms to [Paths Config Structure](#paths-config-structure) |
| **project_filter** | String | A unique docker label that is used to identify containers and images that belong to the project. |
| reprovisionable_components | List of Strings | List of component names that need to reprovisioned (contianer stopped, and removed, then started and provisioned again) if the hosts' IP changes) |
| runtime_images | Hash of Hashes | Defines custom images that components might be using. These images etc.. would provided by, and maintained by the project. First level key is a string of the name of the image. Structure conforms to [Runtime Image Structure](#runtime-image-structure) |
| wizard_enabled | Boolean | Whether or not to try and execute a wizard if found in the root of the project |

## Component Config Structure
The structure looks like this:
```
{
    "image": "",
    "systemd_support": false,
    "enabled": false,
    "cmd": "",
    "ports": [],
    "mounts": [],
    "run_opts": [],
    "pre_scripts: [],
    "scripts": [],
    "post_up_scripts": [],
    "status_script": "",
    "shell": "",
    "ordinal": {
        "group": INT,
        "number": INT 
    },
    "reset_paths": []
}
```

All Keys that are in **bold** are required

| Key | Type  | Value Description |
| --- |  ---  | ---               |
| **image** | String | A docker notation of docker image to use for the component. This can also reference a devlab base image, as well as a project's [runtime image](#runtime-image-structure) | 
| systemd_support | Boolean | If set to `true` then this will start the component with proper `/run`, `/run/lock`, `/tmp`, and `/sys/fs/cgroup` mounts so systemd can run |
| **enabled** | Boolean | Whether or not the component should be brought [up](#up-action) and images [built](#build-action) |
| **_name_** | String | This is only supported for `foreground_components` but required. It indicates the name of the component |
| type | String | This only only supported for `foreground_components`, but can be either `host` or `container`. If set to host then `cmd` is executed on the local system instead of a container |
| cmd | String | This is the command passed to the container as part of the `docker run` command. If `type` is set to `host` then the command is executed on the local system |
| ports | List of Strings | The ports that should be "published" using the same notation as the `--publish` option to `docker run` |
| mounts | List of Strings | List of mounts in the format `SOURCE_ON_HOST:DESTINATION_IN_CONTAINER`. If using a relative path then the paths are relative to the project's root |
| run_opts | List of Strings | Additional options to pass to `docker run`. Each CLI arg must be it's own element. For example: `[ '--ip', '172.30.255.2' ]` would become `docker run --ip 172.30.255.2 IMAGE COMMAND` etc... |
| pre_scripts | List of Strings | Scripts to run *before* starting the component's container. These are only executed the first time a component is started, and are part of the 'provisioning' steps. The string follows the [Script Runner Syntax](#script-runner-syntax) |
| scripts | List of Strings | Scripts to run *after* starting the component's container. These are only excecuted the first time a component is started, and are part of the 'provisioning' steps. The string follows the [Script Runner Syntax](#script-runner-syntax) |
| post_up_scripts | List of Strings | Scripts to run *after* the component has been started and provisioned. These are executed ***EVERY*** single time the component is started. The string follows the [Script Runner Syntax](#script-runner-syntax) |
| status_script | String | Script to run for the component as part of the devlab [status](#status-action) action. The string follows the [Script Runner Syntax](#script-runner-syntax). The output must conform to the [Status Command API](#status-command-api) |
| shell | String | The path to the shell inside the container that will be the default command when using the devlab [sh](#sh-action) action |
| ordinal | Hash | This is used indicate the order of the components. When parallel execution is supported, the `group` key indicates the components that can be brought up at the same time, `number` indicates the order inside the group to start up |
| reset_paths | List of Strings | These are paths to files and diretories relative to the `paths['component_persistence']` that should be deleted when performing a devlab [reset](#reset-action) |

## Network Config Structure
The structure looks like this:
```
{
    "name": "",
    "device_name": "",
    "cidr": ""
}
```

All Keys that are in **bold** are required

| Key | Type  | Value Description |
| --- |  ---  | ---               |
| **name** | String | The name of the docker network to use |
| device_name | String | When creating the network use this name as the network interface on the host |
| cidr | String | The CIDR notation of the network range to use for the new docker network |

***[NOTE]*** All of the above keys are required unless you have pre-created the network.

## Paths Config Structure
The structure looks like this:
```
{
    "component_persistence": "",
    "component_persistence_wizard_paths": [],
    "reset_paths": [],
    "reset_full": []
}
```

All Keys that are in **bold** are required

| Key | Type  | Value Description |
| --- |  ---  | ---               |
| **component_persistence** | String | Relative path to where components are expected to store persistent data. This is used by the `reset_paths` key in [Component Config Structure](#component-config-structure) and is used by the devlab [reset](#reset-action) action |
| component_persistence_wizard_paths | List of Strings | If your project uses a wizard, you can define file names that should be removed from all component that use `component_persistence` as part of a devlab [reset](#reset-action) `--reset-wizard` action |
| reset_paths | List of Strings | Paths to files and directories relative to the devlab project's root, that are more related to devlab, than the project to remove as part of a devlab [reset](#reset-action) `devlab` action |
| reset_full | List of Strings | Paths to files and directories relative to the devlab project's root, that should be removed as part of a devlab [reset](#reset-action) `--full` action |

## Runtime Image Structure
The structure looks like this:
```
{
    "tag": ""|[],
    "docker_file": "",
    "build_opts": [],
    "ordinal": {
        "group": INT,
        "number": INT 
    }
}
```
All Keys that are in **bold** are required

| Key | Type  | Value Description |
| --- |  ---  | ---               |
| **tag** | String or List of Strings | This is a tag that should be applied to the image. If a list is passed, the first tag becomes a primary identifier. |
| **docker_file** | String | Path to the docker file, relative to the project's root to use when building the image. ***[NOTE]*** The build context will be the parent directory of the dockerfile's path |
| build_opts | List of Strings | Additional options to pass to the `docker build` command. Each CLI arg must be it's own element. For example: `[ '--build-arg', 'foo=bar' ]` would become `docker build --build-arg foo=bar PATH...` etc... |
| ordinal | Hash | This is used indicate the order of the images to build. When parallel execution is supported, the `group` key indicates the image that can be built at the same time, `number` indicates the order inside the group to start up |

_**[NOTE]**_ Devlab supports a special label (`last_modified`).
If this label is present in the `docker_file`, then everytime that the devlab project is brought `up`, it will check that the value of the label in the docker image matches the value of `last_modified` in the `docker_file`. If they are different then devlab will rebuild the image. This allows you to ensure that updates to the `docker_file`'s in your runtime images, result in the users of your project getting updated images.

## Script Runner Syntax
The general format of a Script Runner formatted string is:
```
MODE|OPTS: ENV_VAR CMD
```

All Keys that are in **bold** are required

| Key | Value Description |
| --- | ---               |
| MODE | This can be unset or have a value of: `helper_container`, `running_container`, or `host`. If unset inside of a component `script` like declaration, then the command will run within the component's container. If using `host` the command will be run from your local system |
| OPTS | When in `running_container` mode, OPTS will use the [running_container format](#script-runner-running_container-mode)<br >When in `helper_container` mode OPTS will use the [helper_container format](#script-runner-helper_container-mode)|
| ENV_VAR | Using the VARIABLE=VALUE syntax, adding one or more of these in from of the CMD, will pass them as environment variables to CMD |
| **CMD** | Path to a command to run with any args |

Examples:

Execute a `dynamodb.sh` script inside of a container using the `devlab_helper` base image
```
helper_container|devlab_helper:/devlab/scripts/dynamodb.sh --create-tables --endpoint dynamodb-devlab
```

Execute a `haproxy_reload.sh` script inside of the running container `lb-devlab`
```
running_container|lb-devlab:/devlab/scripts/haproxy_reload.sh
```

Execute a `env_test.sh` script inside of a container using the `devlab_helper` base image, on the `latest` tag, with the name `test-env` with environment variables
```
helper_container|devlab_helper^latest^test-env: FOO=BAR SHOO=BAZ /devlab/scripts/env_test.sh
```

Execute a `foo.sh` script inside of the component's main container
```
/devlab/scripts/foo.sh
```

Execute a command on your local system
```
host: /sbin/sysctl -w vm.max_map_count=262144
```

### Script Runner running_container Mode
This mode is for running a command inside of an already running container

The format of `OPTS` is the name of the existing container to run the CMD inside of.

### Script Runner helper_container Mode
This mode is for spinning up a temporary container and CMD inside of it.

The format of OPTS is:
```
IMAGE_NAME^TAG^CONTAINER_NAME
```

All Keys that are in **bold** are required

| Key | Value Description |
| --- | ---               |
| **IMAGE_NAME** | The name of the image to use when creating the helper container |
| TAG | Optional tag of the image to use, defaults to `latest` |
| CONTAINER_NAME | When creating the container give it the specific hostname and container name |

***[NOTE]*** All helper_container containers will get the project's root mounted at `/devlab` inside of the container

## Status Command API
Each component has the ability to have a `status_script` (See [Component Config Structure](#component-config-structure)) that is used by the devlab [status](#status-action) action. This way devlab can get more detailed information about the services in the defined component than just a general port check. This script can be any command, as long as the output from the command outputs JSON in the following structure:

```
{
    "status": {
        "health": ""
    },
    "links": []
}
```

| Key | Type | Value Description |
| --- | ---  | ---               |
| status | Hash | This hash currently only has a single key "health", it's value is a string that will be displayed in the `health` column of the Component Status table |
| links | List of Hashes | If the component provides a service that you would expect to be reachable from your local system, you can output links. Each Link is a "Hash" hash with the following keys `link` and `comment` which are output in the Links table | 

***[NOTE]*** Hashes in the `links` array support string format syntax for the following keys:

| Key | Description |
| --- | ---         |
| container_name | The name of the docker container for the component |
| host_ip | The IP address of the host running devlab |
| local_port | The first docker published port on the host |

Example output:
```
{
    "status": {
        "health": "healthy"
    },
    "links": [
        {
            "link": "http://123.123.123.123",
            "comment": "Main entry point for foobar service"
        }
    ]
}
```

Using String format syntax
```
{
    "status": {
        "health": "healthy"
    },
    "links": [
        {
            "link": "http://{host_ip}",
            "comment": "Main entry point for foobar service"
        }
    ]
}
```

## A Working Devlab Configuration Example
This is an example taken from the `foreground` example in `examples/foreground` which basically spins up a vault server, unseals, stores some data in it and then the main app just gets that data from the vault service
```
{
    "paths": {
        "component_persistence": "persistent_data"
    },
    "domain": "dev.lab",
    "project_filter": "lab.dev.example.type=devlab",
    "wizard_enabled": false,
    "components": {
        "vault": {
            "image": "vault:latest",
            "enabled": true,
            "cmd": "vault server -config /vault/config",
            "run_opts": [
                "-e","VAULT_LOCAL_CONFIG={\"backend\": {\"file\": {\"path\": \"/vault/file\"}}, \"disable_mlock\":true, \"listener\": {\"tcp\": {\"address\": \"0.0.0.0:8200\", \"tls_disable\":1}}"
            ],
            "ports": [
                "8200:8200"
            ],
            "mounts": [
                ":/devlab",
                "persistent_data/vault/data:/vault/file"
            ],
            "post_up_scripts": [
                "VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=ThisIsntARealThing /devlab/scripts/setup_vault.sh"
            ],
            "shell": "/bin/sh",
            "ordinal": {
                "group": 0,
                "number": 1
            },
            "reset_paths": [
                "data/",
                "env",
                "init.out",
                "my_app_token.out"
            ]
        }
    },
    "foreground_component": {
        "name": "my_app_vault",
        "image": "devlab_helper",
        "cmd": "/devlab/scripts/start_my_app.sh",
        "mounts": [
            ":/devlab"
        ],
        "reset_paths": [
            "config.yaml",
            "app_data/"
        ]
    }
}
```

Equivalent in yaml format:
```
---
paths:
  component_persistence: persistent_data
domain: dev.lab
project_filter: lab.dev.example.type=devlab
wizard_enabled: false
components:
  vault:
    image: vault:latest
    enabled: true
    cmd: vault server -config /vault/config
    run_opts:
    - "-e"
    - 'VAULT_LOCAL_CONFIG={"backend": {"file": {"path": "/vault/file"}}, "disable_mlock":true,
      "listener": {"tcp": {"address": "0.0.0.0:8200", "tls_disable":1}}'
    ports:
    - 8200:8200
    mounts:
    - ":/devlab"
    - persistent_data/vault/data:/vault/file
    post_up_scripts:
    - VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=ThisIsntARealThing /devlab/scripts/setup_vault.sh
    shell: "/bin/sh"
    ordinal:
      group: 0
      number: 1
    reset_paths:
    - data/
    - env
    - init.out
    - my_app_token.out
foreground_component:
  name: my_app_vault
  image: devlab_helper
  cmd: "/devlab/scripts/start_my_app.sh"
  mounts:
  - ":/devlab"
  reset_paths:
  - config.yaml
  - app_data/
```

# Devlab Argument documentation
All actions have a `--help` which should display relevent help. The following options below are "global" options and *should* preceed any action:

```
  -h, --help            show this help message and exit
  --log-level, -l {debug,info,warning,error,critical,notset}
                        Set the log-level output
```

The format of the command should be:
`devlab <global options> <action> <action options>`

For example. To bring the environment up with debug level messages:
`devlab -l debug up`

## Actions
```
    build               Build docker images
    down                Bring down components
    sh                  Execute a shell command inside of a
                        component/container
    reset               Reset a specific component, getting rid of all data
                        including persistent data. This is useful if you want
                        to have a component start from scratch without re-
                        running the wizard
    global-status       Get a global status of all environments where devlab
                        has created containers
    status              Get a status of the environment
    up                  Bring up components
    update              Update devlab to the latest released version
```

### Build Action
```
positional arguments:
  {vault,my_app,*}
                        Build the specific image or images. Leave empty for
                        all

optional arguments:
  -h, --help            show this help message and exit
  --clean, -c           Do a clean build, which will remove all images and
                        then rebuild them
  --no-cache, -C        Don't use docker's cache when building
  --pull, -p            Try to pull the latest version of images during build
```

Example:
`devlab build devlab_base --no-cache`

This will (re-)build the devlab_base image without re-using the docker cache

### Down action
```
positional arguments:
  {vault,my_app,*}
                        Bring down the specific component(s)

optional arguments:
  -h, --help            show this help message and exit
  --rm, -r              Don't just bring the component down, but also delete
                        the container
```

Example:
`devlab down -r`

This will stop the containers that are part of the environment and remove them

### Sh action
```
usage: devlab sh [-h] [--adhoc-image ADHOC_IMAGE] [--adhoc-name ADHOC_NAME]
                 [--command ...] [--user USER]
                 [components [components ...]]

positional arguments:
  components            The component(s) or globs where the shell/command
                        should be run. If more than one component is specified
                        the command will be run sequentially across the
                        components. COMPONENTS: my_app_vault, vault, adhoc

optional arguments:
  -h, --help            show this help message and exit
  --adhoc-image ADHOC_IMAGE, -i ADHOC_IMAGE
                        When using the 'adhoc' component, use this image.
                        [NOTE] This is overridden if --command is specified
                        with 'helper_container|IMAGENAME: /bin/bash' etc...
                        DEFAULT: 'devlab_helper'
  --adhoc-name ADHOC_NAME, -n ADHOC_NAME
                        When using the 'adhoc' component, use this name for
                        the container.
  --command ..., -c ...
                        Optional command to run instead of an interactive
                        shell
  --user USER, -u USER  Optional user to run the command/shell as
```

The `adhoc` component allows you to quickly spin up a container using an image of your choosing, in an ephemeral way. As soon as you exit the container, or the --command exits, the container goes away.

***[NOTE]*** The adhoc component does NOT require a devlab configuration, all other components do (obviously)

Examples:
`devlab sh vault`

This will log you into the vault system as the default user (which would be root)

`devlab sh vault -c "echo 'hello world'"`

This will execute the `echo 'hello world'` command inside of the vault container

`devlab sh adhoc`

This will create a new container and give you a shell.

`devlab sh adhoc --adhoc-image ubuntu:18.04`

This will create a new container from the `ubuntu:18.04` image

### Reset action
```
usage: devlab reset [-h] [--reset-wizard] [--full] [targets [targets ...]]

positional arguments:
  targets             Reset the specific target(s) or glob matches. * means
                      all components, but this does NOT inlcude other targets
                      like 'devlab'. TARGETS: my_app_vault, vault, devlab

optional arguments:
  -h, --help          show this help message and exit
  --reset-wizard, -r  Also remove wizard related files so that the wizard will
                      run again for the specified component
  --full, -f          Remove all component specific files, wizard files, as
                      well as devlab files AND potentially files you're
                      working on. BE CAREFUL IF YOU HAVE MANUAL CHANGES PATHS
                      DEFINED IN in 'paths.reset_full'!!
```

This action can also take some special "targets". Currently there is just `devlab` which will reset the files defined in the DevlabConfig file under `paths.reset_paths`. See also: [Paths Config Structure](#paths-config-structure)

In the future there may be other targets, like `docker` etc...

NOTE: A standard `devlab reset` only selects components and no additional targets like `devlab`. However if you forcefully put a '*' in it will successfully match against any target. So `devlab reset '*'` will get all components as well as the `devlab` target. 

Example:
`devlab reset -r vault`

This will reset the vault component so that it can be reprovisioned from scratch

`devlab reset -f`

This will reset the devlab back to a state as if the wizard was never run and there is no persistent storage.

### Restart action
```
usage: devlab restart [-h] [--update-images] [components [components ...]]

positional arguments:
  components           Stop and start a specific component(s) or glob match.
                       COMPONENTS: my_app_vault, vault

optional arguments:
  -h, --help           show this help message and exit
  --update-images, -u  Look for images that components are using, and try to
                       either build new versions, or pull new ones
```

### Status action
There are no optional arguments for this action. This will run any `status_script` (See [Component Config Structure](#component-config-structure)) for more information) and generate a table indicating the health etc... of the components. If not `status_script` is set, then a generic tcp port check is performed on the first published port on the container.

Example output:
```
example@example:/git/devlab/examples/foreground> devlab status
2019-10-24 15:39:09,951 - ScriptRunner-vault-devlab - INFO - Executing command: '/devlab/scripts/status_vault.sh' inside of container: vault-devlab
2019-10-24 15:39:10,383 - ScriptRunner-my_app_vault-devlab - INFO - Executing command: '/devlab/scripts/status_my_app.sh' inside of container: my_app_vault-devlab

## COMPONENT STATUS ##
------------------------------------------------------------------------------------------------
|    Component     |     Container Name     |  Status  |        Health        | Docker exposed |
------------------------------------------------------------------------------------------------
| vault            | vault-devlab           | up       |       healthy        | 8200(tcp)      |
| my_app_vault     | my_app_vault-devlab    | up       |       healthy        |                |
------------------------------------------------------------------------------------------------

## LINKS ##
-----------------------------------------------------------------------------------------------------------------------------------
|    Component     |                 Link(s)                  |                              Comment                              |
-----------------------------------------------------------------------------------------------------------------------------------
| vault            | http://172.17.0.2:8200                   | Vault address endpoint                                            |
|                  |                                          |   - App token: s.qOsndlsTO4Z3j8k8p2HJlIjr                         |
-----------------------------------------------------------------------------------------------------------------------------------
```

### Up action
This brings a component or stack of components up, as well as any provisioning scripts that are set.

```
usage: devlab up [-h] [--bind-to-host] [--skip-provision] [--keep-up-on-error]
                 [--update-images]
                 [components [components ...]]

positional arguments:
  components            Bring up the specific component(s) based on name or
                        glob match. COMPONENTS: my_app_vault, vault

optional arguments:
  -h, --help            show this help message and exit
  --bind-to-host, -b    Whether or not we should spin things up so that other
                        systems on your host's network will be able to easily
                        reach and work with the spun up components. This
                        generally means if your host's IP changes, components
                        will have to be reprovisioned
  --skip-provision, -k  Bring up the components but don't run any of the
                        provisioning scripts
  --keep-up-on-error, -K
                        Whether to keep a component container running even if
                        it encounters errors during provisioning scripts
                        etc...
  --update-images, -u   Look for images that components are using, and try to
                        either build new versions, or pull new ones when
                        bringing them "up"
```
Examples:

`devlab up`

This will bring up all configured components, as well as ensure that all images have been built

`devlab up vault`

This would bring up the components: `vault`

`devlab up vault -K`

This would bring up the `vault` component, and if there are errors during provisioning etc... keep the container runner for debugging.

### Update action
```
usage: devlab update [-h] [--uninstall] [--set-version SET_VERSION]

optional arguments:
  -h, --help            show this help message and exit
  --uninstall, -U       Instead of updated using the installer, uninstall it
  --set-version SET_VERSION, -V SET_VERSION
                        Update/Downgrade to a specific version of devlab
```

Examples:
`devlab update`

This will update to the latest available version

`devlab update -U`

This will Uninstall devlab

`devlab update -V 1.1.1`

This will install version 1.1.1 from the repo
