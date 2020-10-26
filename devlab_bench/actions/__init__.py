"""
Initialize the different action types available
"""
import devlab_bench.actions.build
import devlab_bench.actions.down
import devlab_bench.actions.global_status
import devlab_bench.actions.restart
import devlab_bench.actions.reset
import devlab_bench.actions.shell
import devlab_bench.actions.status
import devlab_bench.actions.up
import devlab_bench.actions.update

__all__ = [
    'build',
    'down',
    'global_status',
    'restart',
    'reset',
    'shell',
    'status',
    'up',
    'update'
]
