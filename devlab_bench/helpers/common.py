"""
Generic helpers that are intended to be used across other modules etc...
"""

import fnmatch
import json
import logging
import os
import platform
import re
import shlex
import socket
import sys
from copy import deepcopy

import devlab_bench #pylint: disable=cyclic-import
from devlab_bench.exceptions import DevlabComponentError

#Python2/3 compatibility
try:
    #Python2
    text_input = globals()['__builtins__'].raw_input #pylint: disable=invalid-name
    from pipes import quote #pylint: disable=unused-import
    try:
        from pathlib2 import Path #pylint: disable=unused-import
    except ImportError:
        class Path(object): #pylint: disable=too-few-public-methods
            """
            Create a Path object that can simulate python3's Path.home()
            """
            @staticmethod
            def home(self=None): #pylint: disable=bad-staticmethod-argument,unused-argument
                """
                Return the expanded path to the user's home
                """
                return os.path.expanduser('~')
except NameError:
    #Python3
    text_input = input #pylint: disable=invalid-name
    quote = shlex.quote #pylint: disable=invalid-name
    from pathlib import Path

try:
    import yaml
    YAML_SUPPORT = True
except ImportError:
    yaml = None
    YAML_SUPPORT = False

#Check to see if we are attached to a TTY
try:
    ISATTY = sys.stdout.isatty()
except AttributeError:
    ISATTY = False

###-- Functions --###
def get_components(filter_list=None, virtual_components=None, enabled_only=True, match_virtual=False, logger=None):
    """
    Try to list available components

    Args:
        filter_list:
            List or String of component(s) or glob matches to filter out
            desired components
        virtual_components:
            List of additional "allowed" components that aren't found in the
            config and should not be filter out
        enable_only:
            Boolean whether to only include 'enabled' components ot not

    Returns:
        List of components, unless filter_list was a string and only one
        components matches. Then the single string will be returned. This is
        primarily useful for argparser doing it's checks.

    """
    config = get_config()
    all_components = []
    components = []
    filter_str = False
    if logger:
        log = logger
    else:
        log = logging.getLogger('get_components')
    log.debug("Looking up components")
    if 'components' not in config:
        log.debug("No 'components' has found in config, checking fallback default/ path")
        config = get_config(fallback_default=True)
    if 'components' in config:
        log.debug("Found 'components' path")
        if enabled_only:
            log.debug("Only adding 'enabled' components to full list")
            all_components = list(filter(lambda comp: config['components'][comp]['enabled'], config['components']))
        else:
            log.debug("Adding all components (whether enabled or not) to the full list")
            all_components = list(config['components'])
    if 'foreground_component' in config:
        log.debug("Found a 'foreground_component', adding to the full list")
        all_components.append(config['foreground_component']['name'])
    if virtual_components:
        if match_virtual:
            all_components += virtual_components
    if filter_list:
        if isinstance(filter_list, str):
            filter_str = True
            filter_list = [filter_list]
        else:
            if len(filter_list) == 1:
                if isinstance(filter_list[0], list):
                    filter_list = filter_list[0]
        log.debug("Comparing full list to filter_list: '%s'", ','.join(filter_list))
        for filt in filter_list:
            if virtual_components:
                if filt in virtual_components:
                    log.debug("Adding '%s' as a virtual component to filtered list", filt)
                    components.append(filt)
                    continue
            comp_found = False
            for a_comp in all_components:
                log.debug("Checking component: %s against filter val: %s", a_comp, filt)
                if filt == a_comp:
                    log.debug("Found exact match: %s == %s", filt, a_comp)
                    comp_found = True
                    if len(filter_list) == 1:
                        components = [a_comp]
                        break
                elif fnmatch.fnmatch(a_comp, filt):
                    comp_found = True
                elif a_comp.startswith(filt):
                    comp_found = True
                else:
                    continue
                log.debug("Adding: '%s' component to filtered list", a_comp)
                components.append(a_comp)
            if not comp_found:
                raise DevlabComponentError("Unknown component: '{}'".format(filt))
    else:
        log.debug("Adding known components to filtered list")
        components = all_components
    if len(components) == 1:
        if filter_str:
            components = components[0]
    else:
        components = sorted(set(components))
    log.debug("Returning filtered components: %s", components)
    return components

def get_config(force_reload=False, fallback_default=False):
    """
    Try to load the main config file
    """
    if devlab_bench.CONFIG and not force_reload:
        return devlab_bench.CONFIG
    loaded_config = {}
    devlab_bench.CONFIG = deepcopy(devlab_bench.CONFIG_DEF)
    for cfile_name in devlab_bench.CONFIG_FILE_NAMES:
        cfile_path = '{}/{}'.format(devlab_bench.PROJ_ROOT, cfile_name)
        cfile_name_split = os.path.splitext(cfile_name)
        if os.path.isfile(cfile_path):
            if cfile_name_split[1] in ('.yaml', 'yml'):
                if not YAML_SUPPORT:
                    print("Found devlab config: {} in yaml format, but the 'yaml' python module is NOT installed. Please install the yaml python module and try again".format(cfile_path))
                    sys.exit(1)
            with open(cfile_path, 'r') as config_file:
                try:
                    if YAML_SUPPORT:
                        loaded_config = yaml.load(config_file, Loader=yaml.SafeLoader)
                    else:
                        loaded_config = json.load(config_file)
                except Exception: #pylint: disable=broad-except
                    exc_type, exc_value = sys.exc_info()[:2]
                    exc_str = "Failed loading config file: '{cfile_path}' {exc_type}: {exc_val}".format(
                        cfile_path=cfile_path,
                        exc_type=exc_type.__name__,
                        exc_val=exc_value
                    )
                    print(exc_str)
                    sys.exit(1)
                break
        elif fallback_default:
            if os.path.isfile('{}/defaults/{}'.format(devlab_bench.PROJ_ROOT, cfile_name)):
                with open('{}/defaults/{}'.format(devlab_bench.PROJ_ROOT, cfile_name), 'r') as config_file:
                    try:
                        if YAML_SUPPORT:
                            loaded_config = yaml.load(config_file, Loader=yaml.SafeLoader)
                        else:
                            loaded_config = json.load(config_file)
                    except Exception: #pylint: disable=broad-except
                        exc_type, exc_value = sys.exc_info()[:2]
                        exc_str = "Failed loading config file: '{cfile_path}' {exc_type}: {exc_val}".format(
                            cfile_path=cfile_path,
                            exc_type=exc_type.__name__,
                            exc_val=exc_value
                        )
                        print(exc_str)
                        sys.exit(1)
                    break
    devlab_bench.CONFIG.update(loaded_config)
    devlab_bench.UP_ENV_FILE = '{}/{}/devlab_up.env'.format(devlab_bench.PROJ_ROOT, devlab_bench.CONFIG['paths'].get('component_persistence', ''))
    return devlab_bench.CONFIG

def get_env_from_file(env_file):
    """
    This reads the file 'env_file' and tries to convert a bash ENV style format
    to a dict... for example:
        MY_VAR='hello'
        OTHER_VAR='world'
    Would become:
        {
            'MY_VAR': 'hello',
            'OTHER_VAR': 'world'
        }

    Returns:
        Generated Dictionary
    """
    conf = {}
    if os.path.isfile(env_file):
        with open(env_file, 'r') as efile:
            for line in efile:
                line = line.strip()
                line_split = line.split('=')
                key = line_split[0]
                val = '='.join(line_split[1:])
                #Strip off enclosing quotes
                for qot in ('"', "'"):
                    if val[0] == qot:
                        val = val[1:]
                        val = val[:-1]
                if val.lower() in ('true', 'false'):
                    val = val.lower()
                    if val == 'true': #pylint: disable=simplifiable-if-statement
                        val = True
                    else:
                        val = False
                conf[key] = val
    return conf

def get_ordinal_sorting(components, config_components):
    """
    Go through the components in the list 'components', and generate a
    sorted list per their ordinal in the config_components
    """
    #First generate a dict of the combined ordinals and components
    ordinals = {}
    ordinal_sorted = []
    log = logging.getLogger('get_ordinal_sorting')
    log.debug("Will be getting ordinal sorting for components: '%s'", ', '.join(components))
    for comp in components:
        try:
            exists = config_components[comp]
            del exists
        except KeyError:
            raise RuntimeError("Unknown component: {}".format(comp))
        try:
            grp = config_components[comp]['ordinal']['group']
        except KeyError:
            grp = 100
        try:
            num = config_components[comp]['ordinal']['number']
        except KeyError:
            num = 100
        ordinals['{}:{}|{}'.format(grp, num, comp)] = comp
    log.debug("Ordinals found for components: %s", ordinals)
    #Get the list of ordinals, and human sort them
    ordinal_list = sorted(tuple(ordinals.keys()), key=human_keys)
    log.debug("Sorted list of ordinals: '%s'", ', '.join(ordinal_list))
    #Generate the sorted list of components by the sorted ordinal
    for ordinal in ordinal_list:
        ordinal_sorted.append(ordinals[ordinal])
    log.debug("Sorted components by ordinal: '%s'", ', '.join(ordinal_sorted))
    return ordinal_sorted

def get_primary_ip():
    """
    Gets the IP address of whichever interface has a default route

    Based on: https://stackoverflow.com/a/28950776
    """
    broadcast_nets = (
        '10.255.255.255',
        '172.31.255.255',
        '192.168.255.255',
        '172.30.255.1'      #This would be the hosts ip for our docker network
    )
    ip = '127.0.0.1'
    for bnet in broadcast_nets:
        skt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't have to be directly reachable
            skt.connect((bnet, 1))
            ip = skt.getsockname()[0]
            break
        except: #pylint: disable=bare-except
            pass
        finally:
            skt.close()
    return ip

def get_proj_root(start_dir=None):
    """
    Try and determine the project's root path

    Args:
        start_dir: String of the path where to start traversing backwards
            looking for the DevlabConfig.json, DevlabConfig.yaml and equivalents in defaults/

    Returns:
        String of the path found, or None if not found
    """
    if not start_dir:
        start_dir = '.'
    start_dir = os.path.abspath(start_dir)
    cur_dir = start_dir
    found = False
    while cur_dir is not None:
        if os.path.basename(cur_dir) != 'defaults':
            for cfile_name in devlab_bench.CONFIG_FILE_NAMES:
                if os.path.isfile('{}/{}'.format(cur_dir, cfile_name)):
                    found = True
                    break
                if os.path.isfile('{}/defaults/{}'.format(cur_dir, cfile_name)):
                    if os.path.isfile('{}/wizard'.format(cur_dir)):
                        found = True
                        break
                    else:
                        sys.stderr.write("Found '{cur_dir}/defaults/{cfile_name}' but no wizard found. Please pre-generate a config file: ({cfile_name}), or create a wizard that will do it for you so we can call it".format(cur_dir=cur_dir, cfile_name=cfile_name))
                        sys.exit(1)
            if found:
                break
        cur_dir = os.path.dirname(cur_dir)
        if cur_dir == '/':
            cur_dir = None
    return cur_dir

def get_runtime_images():
    """
    Try to get a list of available runtime images
    """
    config = get_config()
    if 'runtime_images' not in config:
        config = get_config(fallback_default=True)
        if 'runtime_images' not in config:
            return []
    runtime_images = list(config['runtime_images'].keys())
    runtime_images.sort()
    return runtime_images

def get_shell_components(filter_list):
    """
    Wrapper for get_components so that argparse can check against custom shell
    specific virtual components
    """
    return get_components(filter_list=filter_list, virtual_components=('adhoc',))

def human_keys(astr):
    """
    Sorts keys based on human order.. IE 1 is less than 10 etc..

    alist.sort(key=human_keys) sorts in human order
    """
    keys = []
    for elt in re.split(r'(\d+)', astr):
        elt = elt.swapcase()
        try:
            elt = int(elt)
        except ValueError:
            pass
        keys.append(elt)
    return keys

def is_valid_hostname(hostname):
    """
    Takes a hostname and tries to determine if it is valid or not

    Args:
        hostname: String of the hostname to check

    Returns:
        Boolean if it is valid or not
    """
    # Borrowed from https://stackoverflow.com/questions/2532053/validate-a-hostname-string
    if len(hostname) > 255:
        return False
    if hostname == 'localhost':
        return True
    if hostname.endswith("."): # A single trailing dot is legal
        hostname = hostname[:-1] # strip exactly one dot from the right, if present
    disallowed = re.compile(r"[^A-Z\d-]", re.IGNORECASE)
    return all( # Split by labels and verify individually
        (label and len(label) <= 63 # length is within proper range
         and not label.startswith("-") and not label.endswith("-") # no bordering hyphens
         and not disallowed.search(label)) # contains only legal characters
        for label in hostname.split("."))

def logging_init(level='info'):
    """
    Initialize and set log level
    level is a String of one of:
        'debug'
        'info'
        'warning'
        'error'
        'critical'
        'notset'
    Colorizing was combining multiple ideas in the answers from:
        https://stackoverflow.com/q/384076
    """
    black, red, green, yellow, blue, magenta, cyan, white = range(8) # pylint: disable=unused-variable
    level_colors = {
        logging.WARNING  : 30 + yellow,
        logging.INFO     : 30 + green,
        logging.DEBUG    : 30 + white,
        logging.CRITICAL : 30 + yellow,
        logging.ERROR    : 40 + red
    }
    sequences = {
        'reset': "\033[0m",
        'color': "\033[1;%dm",
        'bold' : "\033[1m"
    }
    #Initialize logging
    try:
        log_level = int(level)
    except ValueError:
        log_level = devlab_bench.LOGGING_LEVELS[level.lower()]
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    #Setup ANSI coloring for the log level name
    if platform.system() != 'Windows' and devlab_bench.ISATTY:
        for l_level in level_colors:
            logging.addLevelName(
                l_level,
                "{bold}{color_seq}{level_name}{reset}".format(
                    color_seq=sequences['color'] % level_colors[l_level],
                    level_name=logging.getLevelName(l_level),
                    **sequences
                )
            )

def port_check(host, port, timeout=2):
    """
    Perform a basic socket connect to 'host' on 'port'.

    Args:
        host: String of the host/ip to connect to
        port: integer of the port to connect to on 'host'
        timeout: integer indicating timeout for connecting. Default=2

    Returns:
        Boolean whether the connection was successful or now
    """
    skt = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    skt.settimeout(timeout)
    try:
        skt.connect((host, int(port)))
        skt.shutdown(socket.SHUT_RDWR)
        return True
    except Exception: ##pylint: disable=broad-except
        return False
    finally:
        skt.close()

def save_env_file(config_dict, dst_file, force_upper_keys=False):
    """
    This takes a simple, single level dict and tries to write it out to
    'dst_file' in a bash style env file. For example:
        {
            'MY_VAR': 'hello',
            'OTHER_VAR': 'world',
            'lower_var': 'foobar'
        }
    Would become a file with the contents of:
        MY_VAR="hello"
        OTHER_VAR="world"
        lower_var="foobar"
    If force_upper_keys is set, then the key 'lower_var' would become LOWER_VAR
    """
    with open(dst_file, 'w') as dfile:
        for key in config_dict:
            val = config_dict[key]
            if force_upper_keys:
                key = key.upper()
            if val in [True, False]:
                val = str(val).lower()
            else:
                val = '"{}"'.format(val)
            dfile.write('{}={}\n'.format(key, val))

def script_runner(script, name, ignore_nonzero_rc=False, interactive=True, log_output=False, log=None, user=None):
    """
    This takes a delvab script string, and executes it inside containers

    Args:
        script: string of the command. There are optional prefixes for the string:
            PREFIXES:
                'helper_container|<IMAGE_NAME^TAG^CONTAINER_NAME>: <SCRIPT>'
                    This will execute the SCRIPT inside of a new container of
                    IMAGE_NAME with TAG, with the name CONTAINER_NAME
                'running_container|<CONTAINER>: <SCRIPT>'
                    This will execute the SCRIPT inside of the already running
                    CONTAINER
                'host: <SCRIPT'
                    This will execute the SCRIPT on your local host
        name: string of the name of the container that this script is related
            to. So a script without a PREFIX, is run inside of this container
            name.
        ignore_nonzero_rc: bool indicating whether errors should create logs
        interactive: bool, whether to run in "interactive" mode or not
        log: Logger object that will be processing logs. Default=None

    Returns:
        tuple where:
            First Element is the return code of the command
            Second Element is either a list of str
    """
    if not log:
        log = logging.getLogger("ScriptRunner-{}".format(name))
    script_parse = script_runner_parse(script)
    cimg = script_parse['cimg']
    if script_parse['name']:
        name = script_parse['name']
    script = script_parse['script']
    script_mode = script_parse['mode']
    if script_mode == 'host':
        script_split = shlex.split(script)
    else:
        script_split = [quote(script_arg) for script_arg in shlex.split(script)]
    script_stripped = []
    script_run_opts = []
    env_map = {}
    if user:
        script_run_opts.append('--user')
        script_run_opts.append(user)
        script_run_opts.append('--workdir')
        script_run_opts.append('/root')
    script_end_env = False
    for script_arg in script_split:
        if '=' in script_arg:
            if not script_end_env:
                log.debug("Found environment variable for script: '%s'", script_arg)
                e_var, e_val = script_arg.split('=')
                env_map[e_var] = e_val
                continue
        script_stripped.append(script_arg)
        script_end_env = True
    log.debug("Full command, including environment variables: '%s'", script)
    script_split = script_stripped
    script_stripped = ' '.join(script_stripped)
    if script_mode == 'helper_container':
        script_run_opts.insert(0, '--rm')
        ctag = 'latest'
        if '^' in cimg:
            cimg_split = cimg.split('^')
            cimg = cimg_split[0]
            if cimg_split[1]:
                ctag = cimg_split[1]
            name = cimg
            if len(cimg_split) > 2:
                name = cimg_split[2]
            log.debug("Found tag: %s for image: %s. Container name will be: %s", ctag, cimg, name)
        log.info("Executing command: '%s' inside of new container: '%s', using image: '%s:%s'", script_stripped, name, cimg, ctag)
        script_ret = devlab_bench.helpers.docker.DOCKER.run_container(
            image='{}:{}'.format(cimg, ctag),
            name=name,
            network=devlab_bench.CONFIG['network']['name'],
            mounts=[
                '{}:/devlab'.format(devlab_bench.PROJ_ROOT)
            ],
            env=env_map,
            background=False,
            interactive=interactive,
            cmd=script_stripped,
            ignore_nonzero_rc=ignore_nonzero_rc,
            logger=log,
            run_opts=script_run_opts,
            log_output=log_output
        )
    elif script_mode == 'host':
        log.info("Executing command: '%s' on local host", script_stripped)
        script_ret = devlab_bench.helpers.command.Command(
            script_split[0],
            args=script_split[1:],
            env=env_map,
            use_shell=True,
            logger=log,
            log_output=log_output,
            ignore_nonzero_rc=ignore_nonzero_rc,
        ).run()
    else:
        log.info("Executing command: '%s' inside of container: %s", script_stripped, name)
        script_ret = devlab_bench.helpers.docker.DOCKER.exec_cmd(
            name=name,
            background=False,
            interactive=interactive,
            env=env_map,
            cmd=script_stripped,
            ignore_nonzero_rc=ignore_nonzero_rc,
            logger=log,
            exec_opts=script_run_opts,
            log_output=log_output
        )
    return script_ret

def script_runner_parse(script):
    """
    Take a script runner syntax and split it depending on mode etc... if needed

    Args:
        script: String in the format of a script runner syntax

    Returns:
        Dict of the results
    """
    parts_dict = {
        'cimg': '',
        'name': '',
        'script': script,
        'mode': ''
    }
    if script.startswith('helper_container|') or script.startswith('running_container|'):
        #Strip off the mode
        script_mode_split = script.split('|')
        parts_dict['mode'] = script_mode_split.pop(0)
        #Recombine script with the mode stripped off
        script = '|'.join(script_mode_split)
        #Find image
        script_split = script.split(':')
        name = script_split[0]
        if '.' in name:
            if is_valid_hostname(name):
                try:
                    next_slash_split = script_split[1].split('/')
                    host_port_check = re.match(r'[0-9]{2,}', next_slash_split[0])
                    if host_port_check:
                        name = '{}:{}/{}'.format(name, host_port_check.string, '/'.join(next_slash_split[1:]))
                        script_split[0] = name
                        del script_split[1]
                        script = ':'.join(script_split)
                except IndexError:
                    pass
        parts_dict['name'] = name
        parts_dict['cimg'] = name
        parts_dict['script'] = script[1+len(name):].strip()
    elif script.startswith('!!') or script.startswith('host:'):
        parts_dict['mode'] = 'host'
        if script.startswith('!'):
            script = script[2:]
        else:
            script = script[5:]
        parts_dict['script'] = script.strip()
    return parts_dict

def unnest_list(to_unnest, sort=True):
    """
    Take a potential list of lists of strings and convert to a single list of strings

    Args:
        to_unnest: list to work on

    Returns:
        None (the list passed it modified in-place)
    """
    # Make sure that if nested list is passed we unwrap them
    for nst in list(to_unnest):
        if isinstance(nst, list):
            to_unnest += nst
            to_unnest.remove(nst)
    if sort:
        to_unnest = sorted(set(to_unnest))
