"""
Module constructor
"""
import os
import logging
from devlab_bench.helpers import YAML_SUPPORT, ISATTY
from devlab_bench.helpers.common import get_proj_root

__all__ = ['exceptions', 'helpers']
__version__ = 'master'

DEVLAB_BENCH_ROOT = os.path.dirname(os.path.realpath(__file__))
DEVLAB_ROOT = os.path.dirname(DEVLAB_BENCH_ROOT)
IMAGES = {
    'devlab_base': {
        'tag': 'latest',
        'docker_file': 'docker/base.Dockerfile',
        'build_opts': [],
        'ordinal': {
            'group': 0,
            'number': 1
        }
    },
    'devlab_helper': {
        'tag': 'latest',
        'docker_file': 'docker/helper.Dockerfile',
        'build_opts': [],
        'ordinal': {
            'group': 1,
            'number': 1
        }
    }
}
CONFIG = {}
CONFIG_FILE_NAMES = ('DevlabConfig.json', 'DevlabConfig.yaml', 'DevlabConfig.yml', 'Devlabconfig.json', 'Devlabconfig.yaml', 'Devlabconfig.yml')
CONFIG_DEF = {
    'domain': 'devlab.lab',
    'wizard_enabled': True,
    'components': {},
    'network': {
        'name': None
    },
    'reprovisionable_components': [],
    'runtime_images': {},
    'paths': {}
}
LOGGING_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
    'notset': logging.NOTSET
}
PROJ_ROOT = get_proj_root()
UP_ENV_FILE = '{}/{}/devlab_up.env'.format(PROJ_ROOT, '.')
