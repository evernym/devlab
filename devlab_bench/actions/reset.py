"""
Things dealing with the 'up' action
"""
import logging
import os
import shutil
import sys

import devlab_bench.helpers.docker
from devlab_bench.helpers import text_input
from devlab_bench.helpers.common import get_components, get_config, get_ordinal_sorting, unnest_list

def action(targets='*', reset_wizard=False, full=False, **kwargs):
    """
    Reset a component/target

    Args:
        targets: list of components/targets to reset
        reset_wizard: bool, Whether or not to remove files related with the
            wizard to allow the wizard to prompt for the component again
        full: bool, whether or not to completely reset everything, including
            files in CONFIG.paths.reset_full

    Returns:
        None
    """
    ignored_args = kwargs
    config = get_config()
    log = logging.getLogger("Reset")
    foreground_comp_name = None
    if 'foreground_component' in config:
        foreground_comp_name = config['foreground_component']['name']
    add_foreground = False
    if isinstance(targets, str):
        targets = [targets]
    unnest_list(targets)
    if '*' in targets:
        components_to_reset = get_components(filter_list=targets)
    else:
        components_to_reset = targets
    components_to_reset = get_reset_components(targets)
    all_components = get_reset_components('default')
    if not config['components'] and not foreground_comp_name:
        log.error("No components have been configured. Try running with the 'up' action or the 'wizard' script directly")
        sys.exit(1)
    if 'linux' in sys.platform.lower():
        if os.geteuid() != 0:
            log.info("Executing reset command from inside of a container")
            cargs = []
            cur_args = list(sys.argv[1:])
            while cur_args:
                arg = cur_args.pop(0)
                #Ignore any previously passed project root
                if arg.startswith('-'):
                    if arg in ['-P', '--project-root']:
                        cur_args.pop(0)
                        continue
                    cargs.append("'{}'".format(arg))
                    if arg not in ['-v', '--version', '-h', '--help']:
                        cargs.append("'{}'".format(cur_args.pop(0)))
                else:
                    #This indicates that we've reached the 'action'
                    break
            cargs.append('reset')
            if reset_wizard:
                cargs.append('--reset-wizard')
            if full:
                cargs.append('--full')
            if isinstance(targets, list):
                for carg in targets:
                    cargs.append("'{}'".format(carg))
            else:
                cargs.append("'{}'".format(targets))
            script_ret = devlab_bench.helpers.docker.DOCKER.run_container(
                image='devlab_helper:latest',
                name='devlab-reset',
                network=config['network']['name'],
                mounts=[
                    '{}:/devlab'.format(devlab_bench.PROJ_ROOT),
                    '{}/devlab:/usr/bin/devlab'.format(devlab_bench.DEVLAB_ROOT),
                    '{}/devlab_bench:/usr/bin/devlab_bench'.format(devlab_bench.DEVLAB_ROOT),
                    '/var/run/docker.sock:/var/run/docker.sock'
                ],
                run_opts=['--rm', '--workdir', '/devlab'],
                background=False,
                interactive=True,
                cmd='/usr/bin/devlab -P /devlab {}'.format(' '.join(cargs)),
                ignore_nonzero_rc=True,
                logger=log
            )
            if script_ret[0] != 0:
                log.error('Execution of devlab reset command inside of container failed')
                sys.exit(1)
            return
    if set(all_components) != set(components_to_reset):
        if full:
            log.error("You have passed specific components, in addition to --full. When using --full, ALL components are assumed")
            sys.exit(1)
    log.debug("Getting current list of containers")
    containers = devlab_bench.helpers.docker.DOCKER.get_containers()[1]
    containers_dict = {}
    for container in containers:
        containers_dict[container['name']] = container
    if foreground_comp_name in components_to_reset:
        components_to_reset.remove(foreground_comp_name)
        add_foreground = True
    if 'devlab' in components_to_reset:
        components_to_reset.remove('devlab') #Devlab isn't a REAL component, so ordinal stuff will fail
        components_to_reset = get_ordinal_sorting(components_to_reset, config['components'])
        components_to_reset.insert(0, 'devlab')
    else:
        components_to_reset = get_ordinal_sorting(components_to_reset, config['components'])
    if add_foreground:
        components_to_reset.insert(0, foreground_comp_name)
    if full:
        #Make sure the user is really REALLY sure
        while True:
            if 'reset_full' in config['paths']:
                reset_full = ','.join(config['paths']['reset_full'])
            else:
                reset_full = 'Not Defined'
            print("WARNING!! This will remove the files/directories '{}', as well as any files 'reset_paths' per component, and wizard files. If you have made any manual changes to files they will be erased!".format(reset_full))
            ans = text_input("Are you sure you want to proceed? (yes/no) ")
            ans = ans.lower()
            if ans not in ['yes', 'no']:
                print("Valid answers are 'yes' or 'no'")
                continue
            break
        if ans == 'yes':
            if not 'devlab' in components_to_reset:
                components_to_reset.insert(0, 'devlab')
            reset_wizard = True
        else:
            log.warning("Aborting!")
            sys.exit(1)
    components_to_reset.reverse()
    for comp in components_to_reset:
        reset_wizard_files = reset_wizard
        if comp == 'devlab':
            continue
        if comp == foreground_comp_name:
            log.info("Resetting files for foreground component: %s", foreground_comp_name)
            comp_config = config['foreground_component']
            comp_config['enabled'] = True
        else:
            comp_config = config['components'][comp]
        if comp_config['enabled']:
            devlab_bench.actions.down.action(components=[comp], rm=True)
        else:
            # Always reset wizard files for components that are disabled
            reset_wizard_files = True
        if reset_wizard_files:
            log.info("Resetting wizard related files for component: '%s'", comp)
            try:
                for wpath in config['paths']['component_persistence_wizard_paths']:
                    full_path = '{PROJ_ROOT}/{comp_pers}/{component}/{path}'.format(
                        PROJ_ROOT=devlab_bench.PROJ_ROOT,
                        comp_pers=config['paths']['component_persistence'],
                        component=comp,
                        path=wpath
                    ).replace('..', '')
                    log.debug("Looking to see if wizard related path exists: '%s'", full_path)
                    if os.path.isfile(full_path):
                        os.remove(full_path)
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path)
            except KeyError:
                pass
        log.info("Resetting files for component: '%s'", comp)
        try:
            for rpath in comp_config['reset_paths']:
                full_path = '{PROJ_ROOT}/{comp_pers}/{component}/{path}'.format(
                    PROJ_ROOT=devlab_bench.PROJ_ROOT,
                    comp_pers=config['paths']['component_persistence'],
                    component=comp,
                    path=rpath
                ).replace('..', '')
                log.debug("Looking to see if path exists: '%s'", full_path)
                if os.path.isfile(full_path):
                    log.debug("Removing file: '%s'", full_path)
                    os.remove(full_path)
                if os.path.isdir(full_path):
                    log.debug("Removing directory: '%s'", full_path)
                    shutil.rmtree(full_path)
        except KeyError:
            pass
    if 'devlab' in components_to_reset:
        log.info("Resetting devlab specific files")
        try:
            for rpath in config['paths']['reset_paths']:
                full_path = '{PROJ_ROOT}/{path}'.format(
                    PROJ_ROOT=devlab_bench.PROJ_ROOT,
                    path=rpath
                ).replace('..', '')
                log.debug("Looking to see if path exists: '%s'", full_path)
                if os.path.isfile(full_path):
                    log.debug("Removing file: '%s'", full_path)
                    os.remove(full_path)
                if os.path.isdir(full_path):
                    log.debug("Removing directory: '%s'", full_path)
                    shutil.rmtree(full_path)
        except KeyError:
            pass
    if full:
        log.info("Resetting paths for 'full' reset")
        try:
            for fpath in config['paths']['reset_full']:
                full_path = '{PROJ_ROOT}/{path}'.format(
                    PROJ_ROOT=devlab_bench.PROJ_ROOT,
                    path=fpath
                ).replace('..', '')
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                if os.path.isfile(full_path):
                    log.debug("Removing file: '%s'", full_path)
                    os.remove(full_path)
        except KeyError:
            pass

def get_reset_components(filter_list):
    """
    Wrapper for get_components so that argparse can check against custome shell
    specific virtual components
    """
    match_virtual = True
    if len(filter_list) == 1:
        if filter_list[0] == 'default':
            filter_list = ['*']
            match_virtual = False
    elif filter_list == 'default':
        filter_list = ['*']
        match_virtual = False
    res = get_components(filter_list=filter_list, virtual_components=('devlab',), match_virtual=match_virtual)
    return res
