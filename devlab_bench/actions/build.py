"""
Things deal with the 'build' action
"""
import json
import logging
import os
import sys

import devlab_bench.helpers.docker
from devlab_bench import DEVLAB_ROOT, IMAGES, PROJ_ROOT
from devlab_bench.helpers.common import get_config, get_ordinal_sorting
from devlab_bench.helpers.docker import docker_obj_status, DockerHelper, get_needed_images

def action(images='*', clean=False, no_cache=False, pull=False, skip_pull_images=None, **kwargs):
    """
    This is responsible for building all the docker images etc...

    Args:
        images: list of images to build, this can also be the string '*'
        clean: boolean indicating whether all images should be removed and
            rebuilt. Default=False
        no_cache: boolean indicating whether or images should re-use cache when
            building. Default=False
        pull: boolean indicating whether a --pull should happen to update base
            images. Default=False
        skip_pull_images: list of image names to skip when 'pull' is specified
            Default=None
    Returns:
        None
    """
    abort = False
    ignored_args = kwargs
    base_images_to_build = []
    runtime_images_dict = None
    runtime_images_to_build = []
    log = logging.getLogger("Build")
    log_output = False
    log.debug("Will build with clean set to: %s", clean)
    log.debug("Will build with no_cache set to: %s", no_cache)
    log.debug("Will build with pull set to: %s", pull)
    config = get_config()
    base_images_dict = dict(IMAGES)
    images_dict = dict(base_images_dict)
    docker_helper = devlab_bench.helpers.docker.DOCKER
    docker_helper_base = DockerHelper(
        labels=[
            'com.lab.type=devlab'
        ],
        common_domain=config['domain']
    )
    if not skip_pull_images:
        skip_pull_images = []
    if not docker_helper:
        log.warning("No docker_helper was passed, using default helper... This is probably not intended?")
        docker_helper = DockerHelper(filter_label='com.lab.type=devlab')
    try:
        runtime_images_dict = dict(config['runtime_images'])
        images_dict.update(runtime_images_dict)
    except KeyError:
        log.info("No runtime_images defined. Skipping...")
    images_to_build = images
    if log.getEffectiveLevel() <= logging.DEBUG:
        log_output = True
    if images == '*':
        needed_images = get_needed_images()
        base_images_to_build = needed_images['base_images']['missing'] + needed_images['base_images']['exists']
        runtime_images_to_build = []
        for rti in needed_images['runtime_images']['missing'] + needed_images['runtime_images']['exists']:
            if ':' in rti:
                rti = rti.split(':')[0]
            runtime_images_to_build.append(rti)
    else:
        for img in images:
            if img in base_images_dict:
                base_images_to_build.append(img)
            else:
                if ':' in img:
                    img = img.split(':')[0]
                runtime_images_to_build.append(img)
    try:
        images_to_build = get_ordinal_sorting(base_images_to_build, base_images_dict)
        images_to_build += get_ordinal_sorting(runtime_images_to_build, runtime_images_dict)
    except RuntimeError:
        log.error("Image(s): '%s' not found. Maybe one of them is an image that is built with the --runtime-images argument??", ','.join(images_to_build))
        sys.exit(1)
    #See if we need to create a network
    if config['network']['name']:
        network_status = docker_obj_status(config['network']['name'], 'network', devlab_bench.helpers.docker.DOCKER, logger=log)[0]
        if network_status['exists'] and not network_status['owned']:
            log.error("Conflicting custom network found! There is already a docker network defined: '%s' , but is not owned by this project", config['network']['name'])
            sys.exit(1)
        if not network_status['exists']:
            log.info("Custom user network: '%s' not found. Creating", config['network']['name'])
            docker_helper.create_network(**config['network'])
    log.debug("The following images will be built: %s", ', '.join(images_to_build))
    for image in images_to_build:
        if isinstance(images_dict[image]['tag'], list):
            image_n_tag = '{}:{}'.format(image, images_dict[image]['tag'][0])
        else:
            image_n_tag = '{}:{}'.format(image, images_dict[image]['tag'])
        image_status = docker_obj_status(image_n_tag, 'image', devlab_bench.helpers.docker.DOCKER, logger=log)[0]
        image_context = os.path.dirname('{}/{}'.format(PROJ_ROOT, images_dict[image]['docker_file']))
        docker_helper_obj = docker_helper
        build_context = PROJ_ROOT
        if image in base_images_to_build: #Override default build context for built-in images
            build_context = DEVLAB_ROOT
            image_context = DEVLAB_ROOT
            docker_helper_obj = docker_helper_base
        images_dict[image]['docker_file_full_path'] = '{}/{}'.format(build_context, images_dict[image]['docker_file'])
        if 'build_opts' not in images_dict[image]:
            images_dict[image]['build_opts'] = []
        if image in base_images_to_build:
            if image_status['exists'] and image_status['owned']:
                log.info("Found old base image: '%s' that has bad labels... Removing so it can be rebuilt", image)
                rm_res = devlab_bench.helpers.docker.DOCKER.rm_image(image)
                if rm_res[0] != 0:
                    log.error("Failed removing image: %s", image)
                    break
                else:
                    for line in rm_res[1]:
                        log.debug(line)
                    log.debug("Successfully removed image: %s", image)
                    image_status['exists'] = False
                    image_status['owned'] = False
        elif image_status['exists'] and not image_status['owned']:
            log.error("Conflicting image found! There is already an image defined: '%s', but is not owned by this project", image_n_tag)
            break
        if clean and image_status['exists']:
            log.info("Removing image: %s", image)
            rm_res = devlab_bench.helpers.docker.DOCKER.rm_image(image)
            if rm_res[0] != 0:
                log.error("Failed removing image: %s", image)
            else:
                for line in rm_res[1]:
                    log.debug(line)
                log.debug("Successfully removed image: %s", image)
        if pull:
            with open(images_dict[image]['docker_file_full_path']) as dfile:
                local_image = False
                for line in dfile.readlines():
                    if line.startswith('FROM '):
                        if line.split()[1].split(':')[0] in images_to_build + skip_pull_images:
                            local_image = True
                            log.debug("Skipping pull, as devlab manages this image's base image")
                            break
                if not local_image:
                    images_dict[image]['build_opts'].append('--pull')
        if no_cache:
            images_dict[image]['build_opts'].append('--no-cache')
        log.info("Building image: %s", image_n_tag)
        # Marshall the image dict to a string to make a true deep copy
        image_args_json = json.dumps(images_dict[image])
        image_args = json.loads(image_args_json)
        del image_args_json
        # Set the docker_file argument to be the full path
        image_args['docker_file'] = image_args['docker_file_full_path']
        del image_args['docker_file_full_path']
        log.debug("image: '%s' context='%s' log_output='%s' other_args='%s'", image, image_context, log_output, image_args)
        bld_res = docker_helper_obj.build_image(image, context=image_context, log_output=log_output, network=config['network']['name'], logger=logging.getLogger('Build-{}'.format(image)), **image_args)
        if bld_res[0] != 0:
            log.error("Failed building image: '%s' Aborting...", image)
            abort = True
            break
        else:
            log.debug("Successfully built image: %s", image)
    log.info("Cleaning up unused devlab images")
    pi_res = devlab_bench.helpers.docker.DOCKER.prune_images()
    if pi_res[0] != 0:
        log.error("Failed cleaning(pruning) images")
    else:
        log.debug("Successfully cleaned up(pruned) images")
    if abort:
        sys.exit(1)
