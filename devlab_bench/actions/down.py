"""
Things deal with the 'down' action
"""
import logging

import devlab_bench.helpers.docker
from devlab_bench.helpers.common import get_config, unnest_list, get_components, get_ordinal_sorting

def action(components='*', rm=False, **kwargs):
    """
    Bring a component down

    Args:
        components: list of components to bring down, this can also be the
            string '*' for all
        rm: bool, Whether to remove the container from docker

    Returns:
        None
    """
    ignored_args = kwargs
    log = logging.getLogger("Down")
    components_to_stop = components
    config = get_config()
    foreground_comp_name = None
    if isinstance(components, str):
        components = [components]
    unnest_list(components)
    if '*' in components:
        components_to_stop = get_components(filter_list=components)
    else:
        components_to_stop = components
    log.debug("Getting current list of containers")
    containers = devlab_bench.helpers.docker.DOCKER.get_containers()[1]
    containers_dict = {}
    for container in containers:
        containers_dict[container['name']] = container
    if 'foreground_component' in config:
        foreground_comp_name = config['foreground_component']['name']
    if foreground_comp_name:
        if foreground_comp_name in components_to_stop:
            components_to_stop.remove(foreground_comp_name)
            components_to_stop = get_ordinal_sorting(components_to_stop, config['components'])
            components_to_stop.append(foreground_comp_name)
        else:
            components_to_stop = get_ordinal_sorting(components_to_stop, config['components'])
    else:
        components_to_stop = get_ordinal_sorting(components_to_stop, config['components'])
    components_to_stop.reverse()
    for comp in components_to_stop:
        comp_cont_name = '{}-devlab'.format(comp)
        try:
            if 'up' in containers_dict[comp_cont_name]['status'].lower():
                log.info("Component: Stopping container: %s...", comp)
                devlab_bench.helpers.docker.DOCKER.stop_container(comp_cont_name)
            else:
                log.info("Component: %s is already stopped. skipping...", comp)
            if rm:
                log.info("Removing container: %s", comp)
                devlab_bench.helpers.docker.DOCKER.rm_container(comp_cont_name, force=True)
        except KeyError:
            log.info("Component: %s has no container. skipping...", comp)
