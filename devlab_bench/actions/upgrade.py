"""
Things dealing with the 'update' action
"""
import logging
import sys

import devlab_bench
from devlab_bench.helpers.command import Command

def action(uninstall=False, set_version=None, **kwargs):
    """
    Attempt to update devlab. This will call sys.exit

    exit code is 0 upon success and 1 if not
    """
    if update_devlab(uninstall=uninstall, set_version=set_version, **kwargs):
        sys.exit(0)
    else:
        sys.exit(1)

def update_devlab(uninstall=False, set_version=None, **kwargs):
    """
    Use the installer to try and update devlab to the latest version in the repo

    Args:
        uninstall: bool, indicating to uninstall instead of update
        set_version: str, indicating a specific version of devlab to install

    Returns:
        Bool, True if successful False if not
    """
    ignored_args = kwargs
    log = logging.getLogger("UpdateDevlab")
    log.debug("Running installer.py to check for updates etc...")
    command = '{}/installer.py'.format(devlab_bench.DEVLAB_ROOT)
    args = []
    if uninstall and set_version:
        log.error("Cannot uninstall a specific version. Uninstall takes no argument")
        return False
    if uninstall:
        args.append('uninstall')
    if set_version:
        args += ['install', '--set-version', set_version]
    inst_out = Command(command, args, interactive=True).run()
    if inst_out[0] != 0:
        log.error("Installer did not exit successfully... Aborting!")
        return False
    return True
