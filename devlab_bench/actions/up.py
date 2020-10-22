"""
Things dealing with the 'up' action
"""
import logging
import os
import sys

import devlab_bench
import devlab_bench.actions.reset
from devlab_bench.helpers.docker import get_needed_images, docker_obj_status, check_custom_registry
from devlab_bench.helpers.common import get_config, get_env_from_file, get_ordinal_sorting, get_shell_components, get_primary_ip, save_env_file, script_runner, unnest_list

def action(components='*', skip_provision=False, bind_to_host=False, keep_up_on_error=False, update_images=False, **kwargs): #pylint: disable=too-many-branches,too-many-statements
    """
    This is responsible for the "up" action, intended to bring up different components

    Args:
        components: list of components to start, this can also be the string *
        skip_provision: bool whether or not the privisioning scripts should be
            skipped when starting up components. Default=False
        bind_to_host: bool whether or not we should spin things up against
            that other systems on your host's network will be able to easily
            work with the spun up components. Default=False
        update_images: bool, whether or not images should be updated with fresh
            layers etc... from docker repo/registry
    Returns:
        None
    """
    up_env = {
        'HOST_IP': get_primary_ip(),
        'BIND_TO_HOST': bind_to_host
    }
    ignored_args = kwargs
    log = logging.getLogger("Run/Up")
    components_to_run = components
    errors = 0
    base_to_build = []
    runtime_to_build = []
    force_reprov = False
    reprovisionable_components = []
    foreground_comp_name = None
    config = get_config()
    up_env_file = '{}/{}/devlab_up.env'.format(devlab_bench.PROJ_ROOT, config['paths']['component_persistence'])
    if 'reprovisionable_components' in config:
        reprovisionable_components = config['reprovisionable_components']
    if 'foreground_component' in config:
        foreground_comp_name = config['foreground_component']['name']
    if isinstance(components, str):
        components = [components]
    unnest_list(components)
    if '*' in components:
        components_to_run = get_shell_components(filter_list=components)
    else:
        components_to_run = components
    log.debug("Components passed: '%s', components_to_run: '%s'", components, components_to_run)
    for comp in components_to_run:
        if comp == foreground_comp_name:
            continue
        if not config['components'][comp]['enabled']:
            log.error("Component: '%s' is not enabled/configured. Aborting", comp)
            sys.exit(1)
    if foreground_comp_name in components_to_run:
        components_to_run.remove(foreground_comp_name)
        components_to_run = get_ordinal_sorting(components_to_run, config['components'])
        components_to_run.append(foreground_comp_name)
    else:
        components_to_run = get_ordinal_sorting(components_to_run, config['components'])
    log.debug("The following components will be started in this order: %s", ', '.join(components_to_run))
    if update_images:
        log.info("Looking for and updating images needed by components: %s", ','.join(components_to_run))
        update_component_images(components=components_to_run)
    needed_images = get_needed_images()
    if needed_images['base_images']['missing'] or needed_images['base_images']['needs_update']:
        base_to_build = needed_images['base_images']['missing'] + needed_images['base_images']['needs_update']
        log.debug("Images: '%s' not found in list of current images", base_to_build)
        if needed_images['base_images']['needs_update']:
            log.info("Found newer dockerfile(s), will update the following base images: %s", ','.join(needed_images['base_images']['needs_update']))
        log.info("Need to build some base images before trying to start containers")
        devlab_bench.actions.build.action(images=base_to_build)
    if config['network']['name']:
        network_status = docker_obj_status(config['network']['name'], 'network', devlab_bench.helpers.docker.DOCKER, logger=log)[0]
        if network_status['exists'] and not network_status['owned']:
            log.error("Conflicting custom network found! There is already a docker network defined with this name, but is not owned by this project")
            sys.exit(1)
        if not network_status['exists']:
            log.info("Custom user network: '%s' not found. Creating", config['network']['name'])
            devlab_bench.helpers.docker.DOCKER.create_network(**config['network'])
    if needed_images['runtime_images']['missing'] or needed_images['runtime_images']['needs_update']:
        runtime_to_build = needed_images['runtime_images']['missing'] + needed_images['runtime_images']['needs_update']
        log.debug("Runtime Images: '%s' not found in list of current images", runtime_to_build)
        log.info("Need to build some runtime images before trying to start containers")
        if needed_images['runtime_images']['needs_update']:
            log.info("Found newer dockerfile(s), will update the following runtime images: %s", ','.join(needed_images['runtime_images']['needs_update']))
        devlab_bench.actions.build.action(images=runtime_to_build)
    if not os.path.isdir('{}/{}'.format(devlab_bench.PROJ_ROOT, config['paths']['component_persistence'])):
        os.mkdir('{}/{}'.format(devlab_bench.PROJ_ROOT, config['paths']['component_persistence']))
    if os.path.isfile(up_env_file):
        prev_env = get_env_from_file(up_env_file)
        if prev_env['BIND_TO_HOST'] != up_env['BIND_TO_HOST']:
            log.warning("Previous devlab environment was stood up with --bind-to-host set to: %s. Starting with the --bind-to-host set to: %s anyway", prev_env['BIND_TO_HOST'], prev_env['BIND_TO_HOST'])
            up_env['BIND_TO_HOST'] = prev_env['BIND_TO_HOST']
    else:
        prev_env = dict(up_env)
    if bind_to_host:
        primary_ip = up_env['HOST_IP']
        prev_primary_ip = prev_env['HOST_IP']
        if primary_ip != prev_primary_ip:
            log.warning("Your host's IP Address has changed from: %s to %s. This means we must re-provision components", prev_primary_ip, primary_ip)
            force_reprov = True
    log.debug("Saving this devlab's environment")
    save_env_file(up_env, up_env_file, force_upper_keys=True)
    log.debug("Getting current list of containers")
    containers = devlab_bench.helpers.docker.DOCKER.get_containers()[1]
    container_names = [cntr['name'] for cntr in containers]
    # Check for any images that depend on custom registry and prompt if missing auth
    if check_custom_registry(components_to_run, config, logger=log):
        log.error("Please make sure you have logged into needed custom docker registries")
        sys.exit(1)
    log.debug("Current list of containers: '%s'", ', '.join(container_names))
    for comp in components_to_run:
        if comp == foreground_comp_name:
            continue
        comp_cont_name = '{}-devlab'.format(comp)
        cont_status = docker_obj_status(comp_cont_name, 'container', devlab_bench.helpers.docker.DOCKER, logger=log)[0]
        if cont_status['exists'] and not cont_status['owned']:
            log.error("Container: '%s' already exists, but is NOT owned by this project!", comp_cont_name)
            errors += 1
            break
        if update_images:
            if cont_status['exists']:
                log.warning("Container: '%s' exists, and we just updated containers, You'll need to restart the container to USE the new image", comp)
        if comp_cont_name in container_names:
            #See if we should reprovision the existing container
            for r_comp in reprovisionable_components:
                if comp.startswith(r_comp):
                    if force_reprov:
                        log.warning("Removing and resetting data in existing container: '%s' as it needs to be reprovisioned", comp_cont_name)
                        devlab_bench.actions.reset.action(comp)
                        log.debug("Refreshing current list of containers")
                        containers = devlab_bench.helpers.docker.DOCKER.get_containers()[1]
        cup_ret = component_up(
            name=comp,
            comp_config=config['components'][comp],
            skip_provision=skip_provision,
            keep_up_on_error=keep_up_on_error,
            current_containers=containers,
            network=config['network']['name'],
            logger=log
        )
        if not cup_ret:
            errors += 1
            break
    if errors == 0:
        if foreground_comp_name:
            if foreground_comp_name in components_to_run:
                del config['foreground_component']['name']
                log.info("Starting the main foreground component: %s", foreground_comp_name)
                fup_ret = component_up(
                    name=foreground_comp_name,
                    comp_config=config['foreground_component'],
                    skip_provision=True,
                    keep_up_on_error=keep_up_on_error,
                    current_containers=containers,
                    network=config['network']['name'],
                    background=False,
                    logger=log
                )
                config['foreground_component']['name'] = foreground_comp_name 
                if not fup_ret:
                    errors += 1
                devlab_bench.actions.down.action()
    if errors > 0:
        sys.exit(errors)
    if update_images:
        log.info("Cleaning up any dangling images")
        pi_res = devlab_bench.helpers.docker.DOCKER.prune_images(prune_all=True)
        if pi_res[0] != 0:
            log.error("Failed cleaning(pruning) images")
        else:
            log.debug("Successfully cleaned up(pruned) images")

def component_up(name, comp_config, skip_provision=False, keep_up_on_error=False, current_containers=None, background=True, network=None, logger=None):
    """
    Bring a component up
    """
    comp = name
    comp_cont_name = '{}-devlab'.format(comp)
    containers_dict = {}
    errors = False
    if logger:
        log = logger
    else:
        log = logging.getLogger('component_up')
    if not current_containers:
        log.debug("Getting current list of containers")
        current_containers = devlab_bench.helpers.docker.DOCKER.get_containers()[1]
    for container in current_containers:
        containers_dict[container['name']] = container
    container_names = [cntr['name'] for cntr in current_containers]
    new_container = True
    while True:
        if comp_cont_name in container_names:
            if 'up' in containers_dict[comp_cont_name]['status'].lower():
                log.info("Component: %s is already running. Skipping...", comp)
                break
            else:
                log.info("Component: %s has already been created, Starting container...", comp)
                devlab_bench.helpers.docker.DOCKER.start_container(comp_cont_name)
                new_container = False
        if new_container:
            if 'mounts' in comp_config:
                mount_list = []
                for mount in comp_config['mounts']:
                    if mount[0] != '/':
                        mount_list.append('{}/{}'.format(devlab_bench.PROJ_ROOT, mount))
                    else:
                        mount_list.append(mount)
                comp_config['mounts'] = list(mount_list)
            if 'run_opts' not in comp_config:
                comp_config['run_opts'] = list()
            if 'pre_scripts' in comp_config:
                for script in comp_config['pre_scripts']:
                    log.debug("Found Pre script: '%s'", script)
                    script_ret = script_runner(script, name=comp_cont_name, log=log)
                    if script_ret[0] != 0:
                        errors = True
                        break
                if errors:
                    break
            log.info("Starting component: %s", comp)
            if not background:
                comp_config['run_opts'].append('--rm')
            run_ret = devlab_bench.helpers.docker.DOCKER.run_container(
                name=comp_cont_name,
                network=network,
                background=background,
                interactive=not background,
                log_output=False,
                **comp_config
            )
            if run_ret[0] == 0:
                log.debug("Successfully started component: '%s' as container: '%s'", comp, comp_cont_name)
            else:
                log.error("FAILED to start component: '%s' as container: '%s'. Aborting...", comp, comp_cont_name)
                if not keep_up_on_error:
                    devlab_bench.actions.down.action(components=[comp], rm=True)
                errors = True
                break
            if 'scripts' in comp_config and not skip_provision:
                for script in comp_config['scripts']:
                    log.debug("Found provisioning script: '%s'", script)
                    script_ret = script_runner(script, name=comp_cont_name, interactive=False, log_output=True)
                    if script_ret[0] != 0:
                        if not keep_up_on_error:
                            devlab_bench.actions.down.action(components=[comp], rm=True)
                        errors = True
                        break
                if errors:
                    if not keep_up_on_error:
                        devlab_bench.actions.down.action(components=[comp], rm=True)
                    break
        if 'post_up_scripts' in comp_config and background:
            for script in comp_config['post_up_scripts']:
                log.debug("Found Post up script: '%s'", script)
                script_ret = script_runner(script, name=comp_cont_name, interactive=False, log_output=True)
                if script_ret[0] != 0:
                    errors = True
                    break
            if errors:
                break
        break
    return not errors

def update_component_images(components=None, logger=None):
    """
    Look through given components and try to build or pull new versions of the
    image layers etc...

    Args:
        components: list, of components to use for finding images to update
        logger: Logger object to use for log messages

    Returns:
        None
    """
    if logger:
        log = logger
    else:
        log = logging.getLogger('update_images')
    log.debug('Looking up images being referenced in components')
    needed_images = get_needed_images(components, logger=log)
    ext_images = needed_images['external_images']['exists'] + needed_images['external_images']['missing']
    int_images = needed_images['base_images']['exists'] + needed_images['base_images']['missing']
    int_images += needed_images['runtime_images']['exists'] + needed_images['runtime_images']['missing']
    log_output = True
    log.info("Building/Updating devlab and project's managed images: '%s'", ','.join(int_images))
    devlab_bench.actions.build.action(int_images, clean=True, pull=True)
    for ext_image in ext_images:
        log.info("Pulling down any updates to image: '%s'", ext_image)
        pi_res = devlab_bench.helpers.docker.DOCKER.pull_image(ext_image, log_output=log_output, logger=log)
        if pi_res[0] != 0:
            log.error("Failed pulling updates for image: %s", ext_image)
            sys.exit(1)
