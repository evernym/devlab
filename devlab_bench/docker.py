"""
Helper classes and/or functions for interacting with docker
"""
import json
import logging
import os
import shlex
import sys
from devlab_bench.helpers import Command

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
