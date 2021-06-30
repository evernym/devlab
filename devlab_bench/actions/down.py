"""
Things deal with the 'down' action
"""
import logging
import os
import time

import devlab_bench.helpers.docker
from devlab_bench.helpers.common import get_config, get_env_from_file, get_components, get_ordinal_sorting, save_env_file, script_runner, script_runner_parse, unnest_list

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
            comp_config = config['foreground_component']
        else:
            comp_config = config['components'][comp]
        comp_type = comp_config.get('type', 'container')
        if comp_type == 'host':
            if 'down_scripts' in comp_config:
                errors = False
                for script in comp_config['down_scripts']:
                    script_parse = script_runner_parse(script)
                    if not script_parse['name']:
                        if not script_parse['mode'] == 'host':
                            log.debug("Assuming Down-script is to be run on host, because the component type is 'host'")
                            script = 'host:{}'.format(script)
                    log.debug("Found Down script: '%s'", script)
                    script_ret = script_runner(script, name=comp_cont_name, interactive=False, log_output=True)
                    if script_ret[0] != 0:
                        errors = True
                        break
                if errors:
                    break
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
                    if 'down_scripts' in comp_config:
                        errors = False
                        for script in comp_config['down_scripts']:
                            log.debug("Found Down script: '%s'", script)
                            script_ret = script_runner(script, name=comp_cont_name, interactive=False, log_output=True)
                            if script_ret[0] != 0:
                                errors = True
                                break
                        if errors:
                            break
                    log.info("Component: Stopping container: %s...", comp)
                    devlab_bench.helpers.docker.DOCKER.stop_container(comp_cont_name)
                else:
                    if 'down_scripts' in comp_config:
                        for script in comp_config['down_scripts']:
                            script_parse = script_runner_parse(script)
                            if not script_parse['name']:
                                if not script_parse['mode'] == 'host':
                                    log.warning("Container already exited. Skipping discovered Post-Down script: '%s'", script)
                                    continue
                    log.info("Component: %s is already stopped. skipping...", comp)
                if rm:
                    log.info("Removing container: %s", comp)
                    devlab_bench.helpers.docker.DOCKER.rm_container(comp_cont_name, force=True)
            except KeyError:
                log.info("Component: %s has no container. skipping...", comp)
        if 'post_down_scripts' in comp_config:
            errors = False
            for script in comp_config['post_down_scripts']:
                log.debug("Found Post-Down script: '%s'", script)
                #Because the component is now down, these scripts can't default to running inside
                #the component container. Check to make sure that the script isn't going to try that
                #and default to running on the host
                script_parse = script_runner_parse(script)
                if not script_parse['name']:
                    if not script_parse['mode'] == 'host':
                        log.warning("Post-Down scripts cannot run inside of the now down container: '%s' defaulting to running on your host. Consider changing your post down script to have a 'host:' prefix to avoid this warning", comp)
                        script = 'host:{}'.format(script)
                script_ret = script_runner(script, name=comp_cont_name, interactive=False, log_output=True)
                if script_ret[0] != 0:
                    errors = True
                    break
            if errors:
                break
