"""
Deals with updating images used by components
"""
import logging
import sys

import devlab_bench.helpers.docker
import devlab_bench.actions.build
from devlab_bench.helpers.docker import get_needed_images

def action(components='*', skip_base_images=False, **kwargs):
    """
    This is for updating images used by components

    Args:
        components: list of components or image names to update, this can also be
            the string '*'
        include_base_images: Bool whether to inlcude the devlab base images when updating
    Returns:
        None
    """
    ignored_args = kwargs
    log = logging.getLogger("UpdateImages")
    if components == '*':
        components = None
    update_component_images(components, skip_base_images=skip_base_images, logger=log)

def update_component_images(components=None, skip_base_images=True, logger=None):
    """
    Look through given components and try to build or pull new versions of the
    image layers etc...

    Args:
        components: list, of components to use for finding images to update
        include_base_images: Bool whether to include base images when updating
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
    int_images = []
    base_images = needed_images['base_images']['exists'] + needed_images['base_images']['missing']
    if not skip_base_images:
        int_images += base_images
    int_images += needed_images['runtime_images']['exists'] + needed_images['runtime_images']['missing']
    log_output = True
    log.info("Building/Updating devlab and project's managed images: '%s'", ','.join(int_images))
    devlab_bench.actions.build.action(int_images, skip_pull_images=base_images, clean=True, pull=True)
    for ext_image in ext_images:
        log.info("Pulling down any updates to image: '%s'", ext_image)
        pi_res = devlab_bench.helpers.docker.DOCKER.pull_image(ext_image, log_output=log_output, logger=log)
        if pi_res[0] != 0:
            log.error("Failed pulling updates for image: %s", ext_image)
            sys.exit(1)
