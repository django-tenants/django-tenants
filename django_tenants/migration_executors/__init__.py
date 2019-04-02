import os

from .base import MigrationExecutor
from .multiproc import MultiprocessingExecutor  # noqa
from .standard import StandardExecutor


def get_executor(codename=None):
    codename = codename or os.environ.get('EXECUTOR', StandardExecutor.codename)

    for klass in MigrationExecutor.__subclasses__():
        if klass.codename == codename:
            return klass

    raise NotImplementedError('No executor with codename %s' % codename)
