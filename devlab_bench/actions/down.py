"""
Things deal with the 'down' action
"""
import logging
import os
import time

import devlab_bench.helpers.docker
from devlab_bench.helpers.common import get_config, get_env_from_file, get_components, get_ordinal_sorting, save_env_file, unnest_list

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
    if os.path.isfile(devlab_bench.UP_ENV_FILE):
        up_env = get_env_from_file(devlab_bench.UP_ENV_FILE)
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
        if comp == foreground_comp_name:
            comp_type = config['foreground_component'].get('type', 'container')
        else:
            comp_type = config['components'][comp].get('type', 'container')
        if comp_type == 'host':
            if up_env.get('{}_PID'.format(comp.upper()), None):
                comp_pid = int(up_env.get('{}_PID'.format(comp.upper()), 0))
                if comp_pid:
                    log.debug('Found pid in devlab up environemnt file for comp: %s, pid: %s', comp, comp_pid)
                    try:
                        os.kill(comp_pid, 0)
                    except OSError:
                        log.info("Component: %s is already stopped. Skipping", comp)
                    else:
                        log.info("Component: %s stopping pid: %s", comp, comp_pid)
                        max_wait_count = 5
                        kill_sent = False
                        wait_count = 0
                        repeating_signal = 15
                        while True:
                            try:
                                os.kill(comp_pid, repeating_signal)
                            except OSError:
                                log.debug("Component: %s pid: %s stopped", comp, comp_pid)
                                del up_env['{}_PID'.format(comp.upper())]
                                save_env_file(up_env, devlab_bench.UP_ENV_FILE, force_upper_keys=True)
                                break
                            if wait_count >= max_wait_count:
                                if kill_sent:
                                    log.error("Component: %s pid: %s won't exit even after KILL signal... Aborting!", comp, comp_pid)
                                    break
                                log.warning("Component: %s pid: %s still hasn't exited. Sending KILL signal", comp, comp_pid)
                                repeating_signal = 0
                                os.kill(comp_pid, 9)
                                kill_sent = True
                                max_wait_count = 3
                                wait_count = 0
                            wait_count += 1
                            time.sleep(1)
                else:
                    log.info("Component: %s has no pid defined and is already stopped. Skipping", comp)
            else:
                log.info("Component: %s has no pid defined and is already stopped. Skipping", comp)
        else:
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
