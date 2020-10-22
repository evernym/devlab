"""
Things dealing with the 'status' action
"""
import json
import logging
import sys

import devlab_bench.helpers.docker
from devlab_bench.helpers.docker import parse_docker_local_ports
from devlab_bench.helpers.common import get_components, get_config, get_primary_ip, get_ordinal_sorting, port_check, script_runner

def action(**kwargs):
    """
    Generates a status of the local devlab environment
    """
    ignored_args = kwargs
    log = logging.getLogger("Status")
    config = get_config()
    foreground_comp_name = None
    if 'foreground_component' in config:
        foreground_comp_name = config['foreground_component']['name']
    log.debug("Getting current list of devlab containers")
    containers = devlab_bench.helpers.docker.DOCKER.get_containers()[1]
    containers_dict = {}
    for container in containers:
        containers_dict[container['name']] = container
    container_names = [cntr['name'] for cntr in containers]
    log.debug("Getting list of configured components")
    cur_components = get_components()
    try:
        if foreground_comp_name in cur_components:
            cur_components.remove(foreground_comp_name)
            components = get_ordinal_sorting(cur_components, config['components'])
            components.append(foreground_comp_name)
        else:
            components = get_ordinal_sorting(cur_components, config['components'])
    except KeyError:
        components = []
    if not components:
        if container_names:
            log.warning("Found orphaned containers: %s", ', '.join(container_names))
            log.warning("It is recommended that you run: 'docker rm -f %s'", ' '.join(container_names))
        else:
            log.info("No components have been configured. Try running with the 'up' action or the 'wizard' script directly")
        sys.exit(1)
    existing_components = list(
        name[0:len(name)-7] for name in list(
            filter(
                lambda cnt_n: cnt_n.endswith('-devlab'), container_names
            )
        )
    )
    running_components = list()
    stopped_components = list()
    missing_components = list()
    for comp in components:
        try:
            if 'up' in containers_dict['{}-devlab'.format(comp)]['status'].lower():
                running_components.append(comp)
            else:
                stopped_components.append(comp)
        except KeyError:
            missing_components.append(comp)
    orphaned_components = list(set(existing_components) - set(components))
    if orphaned_components:
        log.warning("There are orphaned containers: '%s'", ', '.join(orphaned_components))
        log.warning("It is recommended that you run: 'docker rm -f %s'", ' '.join(orphaned_components))
    log.debug("Configured components: '%s'", ', '.join(components))
    log.debug("Current list of running devlab containers: '%s'", ', '.join(container_names))
    log.debug("Current list of all components that exist: '%s'", ', '.join(existing_components))
    log.debug("Current running components: '%s'", ', '.join(running_components))
    log.debug("Building tables")
    status_table = []
    links_table = []
    #Generate Header for Status table
    status_header = {
        'component': 'Component',
        'container_name': 'Container Name',
        'status': 'Status',
        'health': 'Health',
        'local_port': 'Docker exposed'
    }
    status_header_format = "| {component:^16} | {container_name:^22} | {status:^8} | {health:^20} | {local_port:^14} |"
    status_row_format = "| {component:16} | {container_name:22} | {status:8} | {health:^20} | {local_port:14} |"
    status_width = len(status_header_format.format(**status_header))
    status_table_bar = '{{:-<{}}}'.format(status_width)
    status_table.append(status_table_bar.format(''))
    status_table.append(status_header_format.format(**status_header))
    status_table.append(status_table_bar.format(''))
    #Generate Header for Links table
    links_header = {
        'component': 'Component',
        'link': 'Link(s)',
        'comment': 'Comment'
    }
    links_header_format = "| {component:^16} | {link:^40} | {comment:^65} |"
    links_row_format = "| {component:16} | {link:40} | {comment:65} |"
    links_width = len(links_header_format.format(**links_header))
    links_table_bar = '{{:-<{}}}'.format(links_width)
    links_table.append(links_table_bar.format(''))
    links_table.append(links_header_format.format(**links_header))
    links_table.append(links_table_bar.format(''))
    host_ip = get_primary_ip()
    #Print rows
    for comp in components:
        status_row = {
            'component': comp,
            'container_name': '',
            'health': 'unknown',
            'local_port': ''
        }
        format_fillers = {
            'container_name': None,
            'host_ip': host_ip,
            'local_port': None
        }
        status_dict = {}
        status_ports = []
        if comp in existing_components:
            status_row['container_name'] = '{}-devlab'.format(comp)
            format_fillers['container_name'] = status_row['container_name']
        if comp in running_components:
            try:
                first_port = True
                for port in config['components'][comp]['ports']:
                    local_port = parse_docker_local_ports(port)
                    if first_port:
                        status_row['local_port'] = local_port
                        first_port = False
                    else:
                        status_ports.append({
                            'component': '',
                            'container_name': '',
                            'health': '',
                            'status': '',
                            'local_port': local_port
                        })
            except KeyError:
                status_row['local_port'] = ''
            format_fillers['local_port'] = status_row['local_port'].split('(')[0]
            status_row['status'] = 'up'
            status_script = ''
            try:
                status_script = config['components'][comp]['status_script']
                if status_script:
                    log.debug("Found status script: '%s'", status_script)
            except KeyError:
                try:
                    status_script = config['foreground_component']['status_script']
                except KeyError:
                    log.debug("Skipping status script for component: '%s' as none is defined", comp)
                    if format_fillers['local_port']:
                        status_row['health'] = 'healthy'
                        for port in config['components'][comp]['ports']:
                            if 'udp' in port:
                                continue
                            port = parse_docker_local_ports(port)
                            log.debug("Performing basic port check on '%s', port '%s', for health check", comp, port)
                            if not port_check('127.0.0.1', format_fillers['local_port'].split('-')[0].split('(')[0]):
                                log.warning("Basic port status check failed for '%s', port '%s'", comp, port)
                                status_row['health'] = 'degraded'
                            else:
                                log.debug("Basic port status check successful for '%s', port '%s'", comp, port)
            if status_script:
                script_ret = script_runner(status_script, name=status_row['container_name'], interactive=False, log_output=False)
                if script_ret[0] != 0:
                    log.warning("Errors occurred executing status script for component: '%s' Skipping!!", comp)
                else:
                    try:
                        status_dict = json.loads(' '.join(script_ret[1]))
                    except json.decoder.JSONDecodeError:
                        log.warning("Status script: '%s' did NOT return valid JSON for component: '%s', Skipping!!", status_script, comp)
                try:
                    status_row['health'] = status_dict['status']['health']
                except KeyError:
                    pass
                try:
                    first_link = True
                    for link in status_dict['links']:
                        #Fill in any values as results from links support string formatting
                        link = {k: v.format(**format_fillers) for k, v in link.items()}
                        if first_link:
                            links_table.append(links_row_format.format(component=comp, **link))
                            first_link = False
                        else:
                            links_table.append(links_row_format.format(component='', **link))
                except KeyError:
                    pass
        elif comp in stopped_components:
            status_row['status'] = 'stopped'
        else:
            status_row['status'] = 'missing'
        status_table.append(status_row_format.format(**status_row))
        for status_port in status_ports:
            status_table.append(status_row_format.format(**status_port))
    #Generate Footers
    status_table.append(status_table_bar.format(''))
    links_table.append(links_table_bar.format(''))
    print('\n## COMPONENT STATUS ##')
    print('\n'.join(status_table))
    print('')
    if len(links_table) > 4:
        print('## LINKS ##')
        print('\n'.join(links_table))
