"""
Helper classes and/or functions for interacting with docker
"""
import json
import logging
import os
import re
import shlex
import sys

import devlab_bench
from devlab_bench.helpers.command import Command
from devlab_bench.helpers.common import get_components, get_config, Path, is_valid_hostname

DOCKER = None

###-- Classes --###
class DockerHelper(object):
    """
    This is a helper for running docker commands
    """
    def __init__(self, filter_label=None, labels=None, common_domain=None, skip_checks=False):
        """
        Initialize the DockerHelper Object

        Args:
            filter_label: String of a label to filter on when querying docker
            labels: List of labels to apply to all objects created by
                DockerHelper
            common_domain: When running containers, use this domain as part of
                the container name.
        """
        self.log = logging.getLogger('DockerHelper')
        self.docker_bin_paths = (
            '/usr/bin/docker',
            '/usr/local/bin/docker',
            '/usr/sbin/docker',
            '/bin/docker'
        )
        self.filter_label = filter_label
        self.common_domain = common_domain
        self.opt_domainname = False
        if not skip_checks:
            self._pre_check()
        self.labels = labels
    def _pre_check(self):
        """
        Checks to make sure the script is being run as the root user, or a
        user that is able to talk to docker

        Returns None, but if access check fails, then exit
        """
        dchk = Command(self.docker_bin_paths, ['ps'], logger=self.log).run()
        if dchk[0] != 0:
            if os.geteuid() != 0:
                self.log.error("Cannot talk to docker, maybe try again as the root user?")
            else:
                self.log.error("Cannot talk to docker, maybe it isn't running?")
            sys.exit(1)
        dchk = Command(self.docker_bin_paths, ['run', '--help'], logger=self.log, split=False).run()
        if '--domainname' in dchk[1]:
            self.opt_domainname = True
    def build_image(self, name, tag, context, docker_file, apply_filter_label=True, build_opts=None, logger=None, network=None, **kwargs):
        """
        Build a docker image.

        Args:
            name: str, The name of the image
            tag: str or list, Tag(s) to attach to the image
            context: str, Path to the build context to use
            docker_file: str, Path to the Dockerfile to build from
            apply_filter_label: bool, whether to add self.filter as a label to
                the created image
            build_opts: list/tuple, indicating additional options to pass to
                'docker build' (OPTIONAL)
            logger: Logger object to send logs to instead of self.log (OPTIONAL)
            network: str, docker network to attach (OPTIONAL)
            kwargs: dict, Additional arguments to pass to the Command Object
        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        opts = [
            'build',
            '--force-rm'
        ]
        cmd_logger = self.log
        if logger:
            cmd_logger = logger
        if network:
            opts.append("--network={}".format(network))
        if build_opts:
            opts += build_opts
        if self.labels:
            for label in self.labels:
                opts += [
                    '--label',
                    label
                ]
        if self.filter_label and apply_filter_label:
            opts.append('--label={}'.format(self.filter_label))
        if isinstance(tag, list):
            for btag in tag:
                opts += ['-t', '{}:{}'.format(name, btag)]
        else:
            opts += ['-t', '{}:{}'.format(name, tag)]
        opts += [
            '-f',
            '-',
            context
        ]
        if os.path.isfile(docker_file):
            with open(docker_file) as stdin:
                if 'env' in kwargs:
                    kwargs['env'].update({'DOCKER_BUILDKIT': "0"})
                else:
                    kwargs['env'] = {'DOCKER_BUILDKIT': "0"}
                cmd_ret = Command(
                    self.docker_bin_paths,
                    opts,
                    stdin=stdin,
                    logger=cmd_logger,
                    **kwargs
                ).run()
                return cmd_ret
        else:
            self.log.error("Cannot find docker_file: %s", docker_file)
        return (1, ['Cannot find docker_file: {}'.format(docker_file)])
    def create_network(self, name, cidr=None, driver='bridge', device_name=None):
        """
        Create a docker network

        Args:
            name: str, Name of the network to create
            cidr: str, CIDR Notation for the network
        """
        opts = [
            'network',
            'create',
            '--subnet',
            cidr,
            '--driver',
            driver
        ]
        if self.labels:
            for label in self.labels:
                opts += [
                    '--label',
                    label
                ]
        if self.filter_label:
            opts.append('--label={}'.format(self.filter_label))
        if device_name:
            opts.append('--opt')
            opts.append('com.docker.network.bridge.name={}'.format(device_name))
        opts.append(name)
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=self.log
        ).run()
        return cmd_ret
    def exec_cmd(self, name, cmd, background=False, interactive=True, ignore_nonzero_rc=False, logger=None, exec_opts=None, **kwargs):
        """
        Run a command inside of another container

        Args:
            name: str, The name of the container where the command should be run
            cmd: str, Command to run inside the container.
            background: Run the container in the background. (OPTIONAL)
            interactive: bool, whether or not the docker command could require
                console input etc... (OPTIONAL)
            ignore_nonzero_rc: bool indicating whether errors should create
                logs. (OPTIONAL)
            logger: Logger object to send logs to instead of self.log (OPTIONAL)
            exec_opts: list/tuple, indicating additional options to pass to
                'docker exec'. (OPTIONAL)
        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        ignored_opts = kwargs
        opts = [
            'exec',
        ]
        cmd_logger = self.log
        if exec_opts:
            opts += exec_opts
        if background:
            opts.append("--detach")
        if interactive:
            opts.append("-it")
        if logger:
            cmd_logger = logger
        opts += [
            name
        ]
        opts += shlex.split(cmd)
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=cmd_logger,
            interactive=interactive,
            ignore_nonzero_rc=ignore_nonzero_rc,
            **kwargs
        ).run()
        return cmd_ret
    def get_containers(self, return_all=False):
        """
        List of containers that have been created

        Args:
            return_all: bool, whether or not to return all containers
                regardless of the filter set.

        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of dicts from docker if successful,
                    else a list of strings from the output of the command
        """
        opts = [
            'ps',
            '-a'
        ]
        if self.filter_label and not return_all:
            opts.append('--filter')
            opts.append('label={}'.format(self.filter_label))
        opts.append('--format')
        opts.append('{{.ID}},{{.Status}},{{.Names}}')
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=self.log
        ).run()
        containers = []
        if cmd_ret[0] == 0:
            for cres in cmd_ret[1]:
                container_id, status, name = cres.split(',')
                containers.append({
                    'id': container_id,
                    'name': name,
                    'status': status
                })
            return (cmd_ret[0], containers)
        return cmd_ret
    def get_images(self, return_all=False):
        """
        List of images that docker has

        Args:
            return_all: bool, whether or not to return all images regardless of
                the filter set.

        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        opts = [
            'images'
        ]
        if self.filter_label and not return_all:
            opts.append('--filter')
            opts.append('label={}'.format(self.filter_label))
        opts.append('--format')
        opts.append('{{.Repository}}:{{.Tag}}')
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=self.log
        ).run()
        return cmd_ret
    def get_networks(self, return_all=False):
        """
        List of networks that docker has

        Args:
            return_all: bool, whether or not to return all networks regardless
                of the filter set.

        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of dicts from docker if successful,
                    else a list of strings from the output of the command
        """
        opts = [
            'network',
            'list'
        ]
        if self.filter_label and not return_all:
            opts.append('--filter')
            opts.append('label={}'.format(self.filter_label))
        opts.append('--format')
        opts.append('{{.ID}},{{.Name}},{{.Driver}},{{.Scope}}')
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=self.log
        ).run()
        networks = []
        if cmd_ret[0] == 0:
            for nres in cmd_ret[1]:
                network_id, name, driver, scope = nres.split(',')
                networks.append({
                    'id': network_id,
                    'name': name,
                    'driver': driver,
                    'scope': scope
                })
            return (cmd_ret[0], networks)
        return cmd_ret
    def inspect_container(self, container):
        """
        Grabs the inspection data (docker inspect) for a container

        Args:
            container: String of the container you want to inspect

        Return dict
        """
        ret = {}
        cmd_ret = Command(
            self.docker_bin_paths,
            [
                'container',
                'inspect',
                container
            ],
            split=False,
            logger=self.log
        ).run()
        if cmd_ret[0] == 0:
            ret = json.loads(cmd_ret[1])
        return ret
    def inspect_image(self, image):
        """
        Grabs the inspection data (docker inspect) for an image

        Args:
            image: String of the image you want to inspect

        Return dict
        """
        ret = {}
        cmd_ret = Command(
            self.docker_bin_paths,
            [
                'image',
                'inspect',
                image
            ],
            split=False,
            logger=self.log
        ).run()
        if cmd_ret[0] == 0:
            ret = json.loads(cmd_ret[1])
        return ret
    def prune_images(self, prune_all=False):
        """
        Prune images from docker

        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        opts = [
            'image',
            'prune'
        ]
        if self.filter_label and not prune_all:
            opts.append('--filter')
            opts.append('label={}'.format(self.filter_label))
        opts.append('-f')
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=self.log
        ).run()
        return cmd_ret
    def pull_image(self, image, **kwargs):
        """
        Pull an image from docker repos

        Args:
            image: String of the image you want to pull. ie ubuntu:16.04 etc...
            kwargs: dict, Additional arguments to pass to the Command object

        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        opts = [
            'image',
            'pull',
        ]
        opts.append(image)
        if 'logger' not in kwargs:
            kwargs['logger'] = self.log
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            **kwargs
        ).run()
        return cmd_ret
    def rm_container(self, name, force=True):
        """
        Remove a container

        Args:
            name: str, Name of the image to remove
        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        opts = [
            'rm'
        ]
        if force:
            opts.append('-f')
        opts.append(name)
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=self.log
        ).run()
        return cmd_ret
    def rm_image(self, name):
        """
        Remove an image

        Args:
            name: str, Name of the image to remove
        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        cmd_ret = Command(
            self.docker_bin_paths,
            [
                'rmi',
                '-f',
                name
            ],
            logger=self.log
        ).run()
        return cmd_ret
    def run_container(self, image, name, network=None, ports=None, background=True, interactive=False, ignore_nonzero_rc=False, cmd=None, logger=None, mounts=None, systemd_support=False, run_opts=None, **kwargs): #pylint: disable=too-many-arguments
        """
        Run a docker_container

        Args:
            image: str, The name of the image to use for the container
            name: str, The name of the container (this also sets the hostname)
            network: str, docker network to attach
            cmd: str, Command to run inside the container. (OPTIONAL)
            ports: list/tuple, of ports to publish to the host. (OPTIONAL)
            background: Run the container in the background. (OPTIONAL)
            interactive: bool, whether or not the docker command could require
                console input etc... (OPTIONAL)
            ignore_nonzero_rc: bool indicating whether errors should create
                logs. (OPTIONAL)
            logger: Logger object to send logs to instead of self.log (OPTIONAL)
            mounts: list/tuple, Of volume mounts to pass. (OPTIONAL)
            run_opts: list/tuple, indicating additional options to pass to
                'docker run'. (OPTIONAL)
            systemd_support: bool, whether to enable opts to let systemd work
                inside the container. (OPTIONAL)
        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        ignored_opts = kwargs
        opts = [
            'run',
        ]
        cmd_logger = self.log
        if run_opts:
            opts += run_opts
        if self.labels:
            for label in self.labels:
                opts += [
                    '--label',
                    label
                ]
        if self.filter_label:
            opts.append('--label={}'.format(self.filter_label))
        if background:
            opts.append("--detach")
        if network:
            opts.append("--network={}".format(network))
        if systemd_support:
            opts += [
                '--tmpfs=/run',
                '--tmpfs=/run/lock',
                '--tmpfs=/tmp',
                '--volume=/sys/fs/cgroup:/sys/fs/cgroup:ro',
                '-t' #This is needed so that 'docker logs' will show systemd output
            ]
        if mounts:
            for mount in mounts:
                opts.append('--volume={}'.format(mount))
        if ports:
            for port in ports:
                opts.append('--publish={}'.format(port))
        if interactive:
            opts.append('-it')
        if logger:
            cmd_logger = logger
        opts += [
            '--name',
            name
        ]
        if self.common_domain:
            if self.opt_domainname:
                opts += [
                    '--hostname',
                    name,
                    '--domainname',
                    self.common_domain
                ]
            else:
                opts += [
                    '--hostname',
                    '{}.{}'.format(name, self.common_domain)
                ]
        else:
            opts += [
                '--hostname',
                name
            ]
        opts.append(image)
        if cmd:
            opts += shlex.split(cmd)
        cmd_ret = Command(
            self.docker_bin_paths,
            opts,
            logger=cmd_logger,
            interactive=interactive,
            ignore_nonzero_rc=ignore_nonzero_rc,
            **kwargs
        ).run()
        return cmd_ret
    def start_container(self, name, ignore_nonzero_rc=False):
        """
        Start an already existing container

        Args:
            name: str, Name of the container to start
            ignore_nonzero_rc: bool, whether or not we should care if the rc not 0
        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        cmd_ret = Command(
            self.docker_bin_paths,
            [
                'start',
                name
            ],
            ignore_nonzero_rc=ignore_nonzero_rc,
            logger=self.log
        ).run()
        return cmd_ret
    def stop_container(self, name):
        """
        Stop an already existing container

        Args:
            name: str, Name of the container to stop
        Returns:
            tuple where:
                First Element is the return code from docker
                Second Element is a list of strings of the output from docker
        """
        cmd_ret = Command(
            self.docker_bin_paths,
            [
                'stop',
                name
            ],
            logger=self.log
        ).run()
        return cmd_ret

###-- Functions --###
def check_build_image_need_update(image, dockerfile, logger=None):
    """
    Determine if an image needs to be updated based on a dockerfile's
    'last_modified' label. If there is no last_modified label in the dockerfile
    then return will be False.

    Args:
        image: str, of the name of the build image
        dockerfile: str, path to the dockerfile to compare against
        logger: Logger, for to use for logging
    Returns:
        Bool:
            True, if the image needs to be updated
            False, if not
    """
    if logger:
        log = logger
    else:
        log = logging.getLogger('check_build_image_need_update')
    last_modified = 0
    log.debug("Determining if image: '%s' needs to be rebuilt based on 'last_modified' label", image)
    with open(dockerfile) as dfile:
        dfile_contents = dfile.read()
        for df_line in dfile_contents.splitlines():
            if df_line.startswith('LABEL'):
                log.debug("Found LABEL line: '%s'", df_line)
                if 'last_modified' in df_line:
                    log.debug("Found desired 'last_modified' LABEL")
                    last_modified = df_line.split(' ')[1].split('=')[1].strip('"')
                    log.debug("Last modified value in dockerfile: '%s' is '%s'", dockerfile, last_modified)
    if last_modified: #Check if the image has the latest 'last_modified' label
        log.debug("Looking for current last_modified label on existing image: %s", image)
        if not ':' in image:
            image_details = DOCKER.inspect_image('{}:latest'.format(image))[0]['Config']
        else:
            image_details = DOCKER.inspect_image(image)[0]['Config']
        cur_last_modified = None
        for ilabel, ivalue in image_details['Labels'].items():
            log.debug("Found existing label: '%s' on image", ilabel)
            if ilabel == 'last_modified':
                log.debug("Found desired existing 'last_modified' LABEL with a value of '%s'", ivalue)
                cur_last_modified = ivalue
                if last_modified == cur_last_modified:
                    return False
                else:
                    break
        log.debug("Last modified value in dockerfile: '%s' is not the same as current image: '%s'. Update needed", last_modified, cur_last_modified)
        return True
    else:
        log.debug("No last_modified label defined in dockerfile, no update needed")
    return False

def docker_obj_status(name, obj_type, docker_helper, logger=None):
    """
    Determine if a specific docker object like an image, container, or network
    exists, and if it is "owned" by the current project

    Args:
        name: str or list, of the name(s) of the object
        obj_type: str, one of 'network', 'container', 'image', or 'image_bare'
            NOTE:
                'image' includes the tag in the image name. Like: 'stuff:1.0'
                'image_bare' is the image name without the tag.
        docker_helper: DockerHelper, to use for querying docker objects
        logger: Logger, for to use for logging
    Return:
        list of dicts.
        dict structure:
            {
                'name': str, of the object name
                'exists': bool, whether and object with 'name' exists.
                'owned': bool, whether the object is owned by the specific project
            }
    """
    if logger:
        log = logger
    else:
        log = logging.getLogger('docker_obj_status')
    result = list()
    res_tmpl = {
        'name': None,
        'exists': False,
        'owned': False
    }
    owned_obj = list()
    all_obj = list()
    if obj_type == 'network':
        owned_networks = docker_helper.get_networks()[1]
        owned_obj = [net['name'] for net in owned_networks]
        all_networks = docker_helper.get_networks(return_all=True)[1]
        all_obj = [net['name'] for net in all_networks]
    elif obj_type == 'container':
        owned_containers = docker_helper.get_containers()[1]
        owned_obj = [cont['name'] for cont in owned_containers]
        all_containers = docker_helper.get_containers(return_all=True)[1]
        all_obj = [cont['name'] for cont in all_containers]
    elif obj_type == 'image':
        owned_obj = docker_helper.get_images()[1]
        all_obj = docker_helper.get_images(return_all=True)[1]
    elif obj_type == 'image_bare':
        owned_images = docker_helper.get_images()[1]
        owned_obj = [image.split(':')[0] for image in owned_images]
        all_images = docker_helper.get_images(return_all=True)[1]
        all_obj = [image.split(':')[0] for image in all_images]
    else:
        log.warning("Unknown docker object type: '%s'", obj_type)
    if isinstance(name, list):
        for nme in name:
            res = dict(res_tmpl)
            res['name'] = nme
            if nme in owned_obj:
                res['exists'] = True
                res['owned'] = True
            elif nme in all_obj:
                res['exists'] = True
            result.append(res)
    else:
        res = dict(res_tmpl)
        res['name'] = name
        if name in owned_obj:
            res['exists'] = True
            res['owned'] = True
        elif name in all_obj:
            res['exists'] = True
        result.append(res)
    return result

def get_needed_images(components=None, logger=None):
    """
    Look at the configuration and determine which images are needed, depending
    on which components are configured and what they depend on.

    Args:
        logger: Logging, object

    Returns:
        dict:
        {
            'runtime_images': {
                'missing': [],
                'exists': [],
                'exists_owned': [],
                'needs_update': []
            },
            'base_images': {
                'missing': [],
                'exists': [],
                'exists_owned': [],
                'needs_update': []
            },
            'external_images': {
                'missing': [],
                'exists': [],
                'exists_owned': [],
                'needs_update': []
            }
        }
    """
    global DOCKER
    config = get_config()
    if not components:
        components = get_components()
    base_images = list(devlab_bench.IMAGES.keys())
    foreground_comp_name = None
    if 'foreground_component' in config:
        foreground_comp_name = config['foreground_component']['name']
    runtime_images_rdeps = []
    runtime_images_dict = None
    external_images_rdeps = []
    result = {
        'runtime_images': {
            'missing': [],
            'exists': [],
            'exists_owned': [],
            'needs_update': []
        },
        'base_images': {
            'missing': [],
            'exists': [],
            'exists_owned': [],
            'needs_update': []
        },
        'external_images': {
            'missing': [],
            'exists': [],
            'exists_owned': [],
            'needs_update': []
        }
    }
    if logger:
        log = logger
    else:
        log = logging.getLogger('get_needed_images')
    #Get a status for all of the base images, to see if they exist or not
    base_images_status = docker_obj_status(
        name=base_images,
        obj_type='image_bare',
        docker_helper=DOCKER,
        logger=log
    )
    #Find missing/exists, and owned base images:
    for image in base_images_status:
        if not image['exists']:
            log.debug("Base Image/tag: '%s' not found in list of current images: %s", image['name'], base_images)
            result['base_images']['missing'].append(image['name'])
            continue
        else:
            result['base_images']['exists'].append(image['name'])
            if devlab_bench.IMAGES[image['name']]['docker_file'].startswith(devlab_bench.DEVLAB_ROOT):
                docker_file = devlab_bench.IMAGES[image['name']]['docker_file']
            else:
                docker_file = '{}/{}'.format(devlab_bench.DEVLAB_ROOT, devlab_bench.IMAGES[image['name']]['docker_file'])
            if check_build_image_need_update(image=image['name'], dockerfile=docker_file):
                result['base_images']['needs_update'].append(image['name'])
            if image['owned']:
                result['base_images']['exists_owned'].append(image['name'])
    try:
        runtime_images_dict = dict(config['runtime_images'])
    except KeyError:
        log.debug("No runtime_images defined. Skipping...")
    #Find runtime images that are reverse dependencies
    if runtime_images_dict:
        rt_images = list(runtime_images_dict.keys())
    else:
        log.debug("No runtime based images defined. Skipping checks for their reverse dependencies")
        rt_images = []
    #Look for references in components
    for comp in components:
        if comp == foreground_comp_name:
            comp_config = config['foreground_component']
            comp_config['enabled'] = True
        else:
            comp_config = config['components'][comp]
        comp_type = comp_config.get('type', 'container')
        if comp_type == 'host':
            log.debug("Component: %s type is 'host'. No image needed", comp)
            continue
        if comp_config['enabled']:
            comp_img = comp_config['image'].split(':')[0]
            #Found direct dependencies for a component's image
            if comp_img in rt_images:
                image_n_tag = '{}:{}'.format(comp_img, runtime_images_dict[comp_img]['tag'])
                if image_n_tag not in runtime_images_rdeps:
                    log.debug("Discovered needed runtime Image/tag (Direct dependency by component '%s'): '%s'", comp, image_n_tag)
                    runtime_images_rdeps.append(image_n_tag)
            elif comp_img in base_images:
                log.debug("Discovered needed base image (Direct dependency by component '%s'): %s", comp, comp_img)
            else:
                try:
                    tag = comp_config['image'].split(':')[1]
                except IndexError:
                    tag = 'latest'
                image_n_tag = '{}:{}'.format(comp_img, tag)
                if image_n_tag not in external_images_rdeps:
                    log.debug("Discovered needed external Image/tag (Direct dependency by component '%s'): '%s'", comp, image_n_tag)
                    external_images_rdeps.append(image_n_tag)
            #Look for reverse dependencies inside of scripts, status_scripts, pre_scripts, and post_up_scripts
            for script_key in ('scripts', 'status_script', 'pre_scripts', 'post_up_scripts'):
                try:
                    script_cmd = comp_config[script_key]
                except KeyError:
                    continue
                if isinstance(script_cmd, list):
                    for scr in script_cmd:
                        if scr.startswith('helper_container|'):
                            script_image = scr.split(':')[0].split('|')[1]
                            #Found a reverse dependency on a runtime image from a script
                            if script_image in rt_images:
                                itag = runtime_images_dict[script_image]['tag']
                                if isinstance(itag, list):
                                    itag = itag[0]
                                image_n_tag = '{}:{}'.format(script_image, itag)
                                if image_n_tag not in runtime_images_rdeps:
                                    log.debug("Discovered needed runtime Image/tag (runtime from scripts used by component '%s'): '%s'", comp, image_n_tag)
                                    if image_n_tag not in runtime_images_rdeps:
                                        runtime_images_rdeps.append(image_n_tag)
                            elif script_image in base_images:
                                log.debug("Discovered needed base image (from scripts used by component '%s'): %s", comp, script_image)
                            else:
                                try:
                                    tag = script_image.split('^')[1]
                                except IndexError:
                                    tag = 'latest'
                                script_image_tag = '{}:{}'.format(script_image.split('^')[0], tag)
                                if script_image_tag not in external_images_rdeps:
                                    log.debug("Discovered needed external image (from scripts used by component '%s'): %s", comp, script_image_tag)
                                    external_images_rdeps.append(script_image_tag)
                else:
                    if script_cmd.startswith('helper_container|'):
                        script_image = script_cmd.split(':')[0].split('|')[1]
                        #Found a reverese dependency on a runtime images from a script
                        if script_image in rt_images:
                            itag = runtime_images_dict[script_image]['tag']
                            if isinstance(itag, list):
                                itag = itag[0]
                            image_n_tag = '{}:{}'.format(script_image, itag)
                            if image_n_tag not in runtime_images_rdeps:
                                log.debug("Discovered needed runtime Image/tag (runtime from scripts used by component '%s'): '%s'", comp, image_n_tag)
                                runtime_images_rdeps.append(image_n_tag)
                        elif script_image in base_images:
                            log.debug("Discovered needed base image (from scripts used by component '%s'): %s", comp, script_image)
                        else:
                            try:
                                tag = script_image.split('^')[1]
                            except IndexError:
                                tag = 'latest'
                            script_image_tag = '{}:{}'.format(script_image.split('^')[0], tag)
                            if script_image_tag not in external_images_rdeps:
                                log.debug("Discovered needed external image (from scripts used by component '%s'): %s", comp, script_image_tag)
                                external_images_rdeps.append(script_image_tag)
    runtime_images_status = docker_obj_status(
        name=runtime_images_rdeps,
        obj_type='image',
        docker_helper=DOCKER,
        logger=log
    )
    for rt_image in runtime_images_status:
        if not rt_image['exists']:
            log.debug("Runtime Image/tag: '%s' not found in list of current images: %s", rt_image['name'], runtime_images_rdeps)
            result['runtime_images']['missing'].append(rt_image['name'].split(':')[0])
            continue
        else:
            if check_build_image_need_update(
                    image=rt_image['name'],
                    dockerfile='{}/{}'.format(
                        devlab_bench.PROJ_ROOT,
                        runtime_images_dict[
                            rt_image['name'].split(':')[0]
                        ]['docker_file']
                    )
                ):
                result['runtime_images']['needs_update'].append(rt_image['name'])
            result['runtime_images']['exists'].append(rt_image['name'].split(':')[0])
            if rt_image['owned']:
                result['runtime_images']['exists_owned'].append(rt_image['name'].split(':')[0])
    external_images_status = docker_obj_status(
        name=external_images_rdeps,
        obj_type='image',
        docker_helper=DOCKER,
        logger=log
    )
    for ext_image in external_images_status:
        if not ext_image['exists']:
            log.debug("External Image/tag: '%s' not found in list of current images: %s", ext_image['name'], runtime_images_rdeps)
            result['external_images']['missing'].append(ext_image['name'])
            continue
        else:
            result['external_images']['exists'].append(ext_image['name'])
            if ext_image['owned']:
                result['external_images']['exists_owned'].append(ext_image['name'])
    return result

def check_custom_registry(components=None, config=None, logger=None):
    """
    Checks through components for any images that use a custom docker registry
    if any are found then return True. If none are found, then return False

    Args:
        components: list of component names to check in the config. If None
            then look through ALL defined components
        config: Dict of the devlab configuration. If None, then look/load it up

    Returns:
        Boolean.
            True if there is an image that uses a custom registry but no auth
                has been found
            False if there are not images that use a custom registry
    """
    docker_config_loaded = False
    foreground_comp_name = None
    if logger:
        log = logger
    else:
        log = logging.getLogger('check_custom_registry')
    if not config:
        config = get_config()
    if not components:
        components = list(config['components'].keys())
    docker_config = {
        'auths': {}
    }
    if 'foreground_component' in config:
        foreground_comp_name = config['foreground_component']['name']
    for comp in components:
        if comp == foreground_comp_name:
            cmpt = config['foreground_component']
        else:
            cmpt = config['components'][comp]
        comp_type = cmpt.get('type', 'container')
        if comp_type == 'host':
            log.debug("Component: %s type is 'host'. No registry or image needed to lookup", comp)
            continue
        image_host = parse_docker_image_string(cmpt['image'])['host']
        if image_host:
            if not docker_config_loaded:
                docker_config_path = '{}/.docker/config.json'.format(Path.home())
                if os.path.isfile(docker_config_path):
                    with open(docker_config_path) as dcf:
                        docker_config.update(json.load(dcf))
                docker_config_loaded = True
            try:
                auth_str = docker_config['auths'][image_host] #pylint: disable=unused-variable
            except KeyError:
                #Need to auth to the docker registry
                log.warning("This project is using a docker image hosted on the custom registry: %s, and you appear to have never authenticated to it. \n\nPlease execute:\n    docker login %s\n\nThen try again", image_host, image_host)
                return True
    return False

def parse_docker_image_string(image):
    """
    Take a docker image string and break it into different parts:
        image: The original image passed in
        host: Custom registry host. None if it is the default docker hub
        bare_image: The image with the tag and host stripped off
        tag: The tag of the image
    """
    parsed = {
        'image': None,
        'bare_image': '',
        'tag': None,
        'host': None
    }
    parse_image_split = image.split('/')
    host_check = parse_image_split[0]
    host_check_no_port = host_check
    if ':' in host_check:
        host_port_split = host_check.split(':')
        host_port_check = re.match(r'[0-9]{2,5}$', host_port_split[1])
        if host_port_check:
            host_check_no_port = host_port_split[0]
    if ':' in host_check and is_valid_hostname(host_check_no_port) and len(parse_image_split) > 1:
        parsed['host'] = host_check
        parsed['bare_image'] = '/'.join(parse_image_split[1:])
    else:
        parsed['bare_image'] = image
    parsed['image'] = image
    if ':' in parsed['bare_image']:
        tag_split = parsed['bare_image'].split(':')
        parsed['bare_image'], parsed['tag'] = tag_split
    else:
        parsed['tag'] = 'latest'
    return parsed

def parse_docker_local_ports(docker_ports):
    """
    Take a docker publish port formatted string and return the local port

    Args:
        docker_ports: string representation of a docker port publish format

    Returns:
        The parsed local port string
    """
    if not isinstance(docker_ports, list):
        port_split = docker_ports.split(':')
    else:
        port_split = docker_ports
    if '/' in docker_ports:
        proto = docker_ports.split('/')[1]
    else:
        proto = 'tcp'
    try:
        localport = int(port_split[0], base=10)
        return "{}({})".format(localport, proto)
    except ValueError:
        port_range = port_split[0].split('-')
        if len(port_range) != 2:
            port_string_tail = parse_docker_local_ports(port_split[1:])
            return "{}({})".format(port_string_tail, proto)
        return "{}-{}({})".format(port_range[0], port_range[1], proto)
