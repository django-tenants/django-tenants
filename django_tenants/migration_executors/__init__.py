from .base import MigrationExecutor
from .multiproc import MultiprocessingExecutor
from .standard import StandardExecutor


def get_executor(codename=None):
    codename = codename or StandardExecutor.codename

    for klass in MigrationExecutor.__subclasses__():
        if klass.codename == codename:
            return klass

    raise NotImplementedError('No executor with codename %s' % codename)