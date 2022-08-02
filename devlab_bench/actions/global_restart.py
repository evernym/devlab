"""
Things dealing with the 'global_restart' action
"""
import sys
import logging

import devlab_bench
from devlab_bench.helpers.common import get_config
from devlab_bench.helpers.docker import DockerHelper
def action(**kwargs):
    """
    Restart all containers spun up with devlab across all environments
    """
    log = logging.getLogger('Global-Restart')
    restart_args = kwargs
    global_devlab_docker = DockerHelper(
        filter_label='com.lab.type=devlab'
    )
    containers = global_devlab_docker.get_containers()[1]
    project_map = {}
    log.info("Devlab related containers to restart: '%s'", containers)
    for cont in containers:
        cont_name = cont['name']
        comp_name = cont_name
        comp_logger = logging.getLogger('{}-{}'.format(log.name, cont_name))
        details = global_devlab_docker.inspect_container(cont_name)[0]
        labels = details['Config']['Labels']
        container_project = None
        for label in labels:
            if label == 'com.lab.project':
                container_project = labels[label]
                break
        if not container_project:
            log.error('Container: "%s" does not have a project path defined in the label "com.lab.project"', cont_name)
            sys.exit(1)
        if cont_name.endswith('-devlab'):
            comp_name = cont_name[0:len(cont_name)-7]
        try:
            project_map[container_project]['components'].append(comp_name)
        except KeyError:
            project_map[container_project] = {
                'components': [comp_name]
            }
    for project in project_map:
        restart_args['components'] = []
        comp_logger.info('Performing restarts for project at path: %s', project)
        comp_logger.debug('Project components to restart: "%s"', ','.join(project_map[project]['components']))
        #Switch to other Devlab env:
        devlab_bench.PROJ_ROOT = project
        devlab_bench.CONFIG = get_config(force_reload=True)
        devlab_bench.helpers.docker.DOCKER = DockerHelper(
            labels=[
                'com.lab.type=devlab',
                'com.lab.project={}'.format(project),
                devlab_bench.CONFIG['project_filter']
            ]
        )
        #Customize the components to pass to the restart action
        restart_args['components'] = project_map[project]['components']
        #Execute the restart action
        devlab_bench.actions.restart.action(logger=logging.getLogger('{}-{}'.format(comp_logger.name, 'Restart')), **restart_args)
    sys.exit(0)
