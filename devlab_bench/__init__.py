"""
Module constructor
"""
import sys
import devlab_bench.exceptions

__all__ = ['docker', 'exceptions', 'helpers', 'ISATTY', 'YAML_SUPPORT']
__version__ = 'master'

try:
    import yaml
    YAML_SUPPORT = True
except ImportError:
    YAML_SUPPORT = False

#Check to see if we are attached to a TTY
try:
    ISATTY = sys.stdout.isatty()
except AttributeError:
    ISATTY = False
