"""
Generic helpers that are intended to be used across other modules etc...
"""

import fnmatch
import json
import logging
import os
import re
import shlex
import socket
import sys
from copy import deepcopy

import devlab_bench
from devlab_bench.exceptions import DevlabComponentError

#Python2/3 compatibility
try:
    #Python2
    text_input = raw_input #pylint: disable=invalid-name
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
    return devlab_bench.CONFIG

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
    #Get the list of ordinals, and human sort them
    ordinal_list = sorted(tuple(ordinals.keys()), key=human_keys)
    log.debug("Sorted list of ordinals: '%s'", ', '.join(ordinal_list))
    #Generate the sorted list of components by the sorted ordinal
    for ordinal in ordinal_list:
        ordinal_sorted.append(ordinals[ordinal])
    log.debug("Sorted components by ordinal: '%s'", ', '.join(ordinal_sorted))
    return ordinal_sorted

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
    while cur_dir != None:
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

#def set_config(config):
#    """
#    Set's the global config to the 'config'
#
#    Args:
#        config: dict
#
#    Returns:
#        None
#    """
#    global CONFIG
#    CONFIG = config
#
#def set_proj_root(proj_root):
#    """
#    Set's the global PROJ_ROOT to 'proj_root'
#
#    Args:
#        proj_root: str of the patht to the project's root
#
#    Returns:
#        None
#    """
#    global PROJ_ROOT
#    PROJ_ROOT = proj_root
