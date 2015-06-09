# -*- coding: utf-8 -*-
# Author: Douglas Creager <dcreager@dcreager.net>
# This file is placed into the public domain.

# Calculates the current version number.  If possible, this is the
# output of “git describe”, modified to conform to the versioning
# scheme that setuptools uses.  If “git describe” returns an error
# (most likely because we're in an unpacked copy of a release tarball,
# rather than in a git working copy), then we fall back on reading the
# contents of the VERSION file.
#
# To use this script, simply import it your setup.py file, and use the
# results of get_git_version() as your package version:
#
# from version import *
#
# setup(
#     version=get_git_version(),
#     .
#     .
#     .
# )
#
# This will automatically update the VERSION file, if
# necessary.  Note that the VERSION file should *not* be
# checked into git; please add it to your top-level .gitignore file.
#
# You'll probably want to distribute the VERSION file in your
# sdist tarballs; to do this, just create a MANIFEST.in file that
# contains the following line:
#
#   include VERSION

__all__ = ("get_git_version")

from subprocess import Popen, PIPE


def call_git_describe():
    try:
        p = Popen(['git', 'describe', '--tags', '--always'],
                  stdout=PIPE, stderr=PIPE)
        p.stderr.close()
        line = p.stdout.readlines()[0]
        return line.strip().decode('utf-8')

    except:
        return None


def read_release_version():
    try:
        f = open("VERSION", "r")

        try:
            version = f.readlines()[0]
            return version.strip()

        finally:
            f.close()

    except:
        return None


def write_release_version(version):
    f = open("VERSION", "w")
    f.write("%s\n" % version)
    f.close()


def get_git_version():
    # Read in the version that's currently in VERSION.

    release_version = read_release_version()

    # First try to get the current version using “git describe”.

    version = call_git_describe()

    # If that doesn't work, fall back on the value that's in
    # VERSION.

    if version is None:
        version = release_version

    # If we still don't have anything, that's an error.

    if version is None:
        raise ValueError("Cannot find the version number!")

    # If the current version is different from what's in the
    # VERSION file, update the file to be current.

    if version != release_version:
        write_release_version(version)

    # Finally, return the current version.
    return version[1:]


if __name__ == "__main__":
    print(get_git_version())
