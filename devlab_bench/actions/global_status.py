"""
Things dealing with the 'global_satus' action
"""
import sys

from devlab_bench.helpers.docker import DockerHelper
def action(**kwargs):
    """
    Generates a global status of all environments spun up with devlab
    """
    ignored_args = kwargs
    global_devlab_docker = DockerHelper(
        filter_label='com.lab.type=devlab'
    )
    containers = global_devlab_docker.get_containers()[1]
    status_by_project = {}
    status_header = {
        'container_name': 'Container Name',
        'status': 'Status',
        'local_port': 'Docker exposed'
    }
    status_table_head = []
    status_header_format = "| {container_name:^21} | {status:^10} | {local_port:^32} |"
    status_row_format = "| {container_name:21} | {status:10} | {local_port:32} |"
    status_width = len(status_header_format.format(**status_header))
    status_table_bar = '{{:-<{}}}'.format(status_width)
    status_table_head.append(status_table_bar.format(''))
    status_table_head.append(status_header_format.format(**status_header))
    status_table_head.append(status_table_bar.format(''))
    for cont in containers:
        first_port = True
        exposed_ports = False
        status_row = {
            'container_name': cont['name'],
            'status': '',
            'local_port': ''
        }
        rows = []
        state = cont['status']
        details = global_devlab_docker.inspect_container(cont['name'])[0]
        labels = details['Config']['Labels']
        container_project = 'ORPHANED (Unknown project origin)'
        for label in labels:
            if label == 'com.lab.project':
                container_project = labels[label]
                break
        if 'up' in state.lower():
            status_row['status'] = 'up'
        else:
            status_row['status'] = 'stopped'
        for port in details['HostConfig']['PortBindings']:
            exposed_ports = True
            cont_port, port_proto = port.split('/')
            host_port = details['HostConfig']['PortBindings'][port][0]['HostPort']
            port_str = 'Host: {host_port}({proto}) -> Cont: {cont_port}'.format(proto=port_proto, host_port=host_port, cont_port=cont_port)
            if first_port:
                status_row['local_port'] = port_str
                rows.append(status_row)
                first_port = False
            else:
                rows.append({
                    'container_name': '',
                    'status': '',
                    'local_port': port_str
                })
        if not exposed_ports:
            rows.append(status_row)
        try:
            status_by_project[container_project] += rows
        except KeyError:
            status_by_project[container_project] = []
            status_by_project[container_project] += rows
    for project in status_by_project:
        print("##\n## Project: \n##  {}\n##".format(project))
        print('\n'.join(status_table_head))
        for row in status_by_project[project]:
            print(status_row_format.format(**row))
        print(status_table_bar.format(''))
        print('')
    sys.exit(0)
