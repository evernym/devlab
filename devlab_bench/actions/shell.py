"""
Things dealing with the 'up' action
"""
import logging
import sys

import devlab_bench.helpers.docker
from devlab_bench.helpers.docker import check_custom_registry, parse_docker_image_string
from devlab_bench.helpers.common import get_config, get_shell_components, script_runner, unnest_list

def action(components='*', adhoc_image=None, adhoc_name=None, command=None, user=None, **kwargs):
    """
    Execute a shell or a command inside of a component

    Args:
        adhoc_image: string of the image to use for adhoc shell action
        adhoc_name: string of the name to use for the container's name
        components: string or list of the component(s) to shell or execute
            a command on. If more than one component is specified then run the
            command on them sequentially
        command: string of the command to run. Optional. Default=None
        user: string of the user to execute the shell command as
    Returns:
        None
    """
    ignored_args = kwargs
    log = logging.getLogger("Shell")
    if isinstance(components, str):
        components = [components]
    unnest_list(components)
    if '*' in components:
        components_dst = get_shell_components(filter_list=components)
    else:
        components_dst = components
    if isinstance(command, list):
        command = ' '.join(command)
    config = get_config()
    #Remove duplicates
    components_dst = list(sorted(set(components_dst)))
    for component in components_dst:
        if not command:
            try:
                command = config['components'][component]['shell']
            except KeyError:
                command = '/bin/bash'
        ignore_nonzero_rc = bool(command.endswith('/bin/bash') or command.endswith('/bin/sh'))
        if component != 'adhoc':
            log.debug("Getting current list of containers")
            containers = devlab_bench.helpers.docker.DOCKER.get_containers()[1]
            containers_dict = {}
            for container in containers:
                containers_dict[container['name']] = container
            container_names = [cntr['name'] for cntr in containers]
            log.debug("Current list of containers: '%s'", ', '.join(container_names))
            try:
                if 'up' not in containers_dict['{}-devlab'.format(component)]['status'].lower():
                    log.error("Component: %s is not currently running. Aborting", component)
                    sys.exit(1)
            except KeyError:
                log.error("Container %s-devlab doesn't currently exist for component: %s. Try doing an 'up' action first? Aborting", component, component)
        else:
            if not (command.startswith('helper_container|') or command.startswith('running_container|')):
                log.debug("Building adhoc command...")
                adhoc_image_parsed = parse_docker_image_string(adhoc_image)
                log.debug("Adhoc image tag: %s", adhoc_image_parsed['tag'])
                if adhoc_image_parsed['host']:
                    adhoc_image_parsed['host'] += '/'
                    adhoc_config = {
                        'components': {
                            'adhoc': {
                                'image': adhoc_image
                            }
                        }
                    }
                    if check_custom_registry(['adhoc'], adhoc_config, logger=log):
                        log.error("Please make sure you have logged into needed custom docker registries")
                        sys.exit(1)
                else:
                    adhoc_image_parsed['host'] = ''
                if not adhoc_name:
                    adhoc_name = adhoc_image_parsed['bare_image']
                    adhoc_name = '{}-adhoc'.format(adhoc_name.replace('/', '_').strip('_'))
                command = 'helper_container|{host}{bare_image}^{tag}^{adhoc_name}: {command}'.format(adhoc_name=adhoc_name, command=command, **adhoc_image_parsed)
                log.debug("Built adhoc command: '%s'", command)
        script_runner(command, '{}-devlab'.format(component), log=log, ignore_nonzero_rc=ignore_nonzero_rc, user=user)
