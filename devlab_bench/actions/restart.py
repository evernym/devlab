"""
Things deal with the 'restart' action
"""
import logging

import devlab_bench.actions.down
import devlab_bench.actions.up
from devlab_bench.helpers.common import get_components, unnest_list
def action(components='*', logger=None, update_images=False, **kwargs):
    """
    Restart components by bringing them down and then back up again

    Args:
        update_images: bool, whether or not to try and update images that components rely upon
    """
    #restart
    ignored_args = kwargs
    if logger:
        log = logger
    else:
        log = logging.getLogger('Restart')
    components_to_restart = components
    rm = False
    if isinstance(components, str):
        components = [components]
    unnest_list(components)
    if '*' in components:
        components_to_restart = get_components(filter_list=components)
    else:
        components_to_restart = components
    if update_images:
        rm = True
    log.info("Bringing components DOWN")
    devlab_bench.actions.down.action(components=components_to_restart, rm=rm)
    log.info("Bringing components UP")
    devlab_bench.actions.up.action(components=components_to_restart, update_images=update_images)
