#  Copyright 2020-2026 Robert Bosch GmbH
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# *******************************************************************************
#
# File: setup.py
#
# Initially created by Nguyen Huynh Tri Cuong (MS/EMC51) / January 2026.
#
# Description:
#   Extended setup script for ProcessHub package installation.
#   Extends the standard setuptools installation by adding documentation
#   and tidying up some folders.
#
# Usage:
#   python setup.py install        # Install the package
#   python setup.py develop        # Install in development mode
#   python setup.py bdist_wheel    # Build wheel distribution
#
# *******************************************************************************

import os
import sys
import setuptools
from setuptools.command.install import install

# prefer the repository local version of all additional libraries
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "./additions")))

from config.CRepositoryConfig import CRepositoryConfig
from additions.CExtendedSetup import CExtendedSetup

import colorama as col

col.init(autoreset=True)

COLBR = col.Style.BRIGHT + col.Fore.RED
COLBY = col.Style.BRIGHT + col.Fore.YELLOW
COLBG = col.Style.BRIGHT + col.Fore.GREEN

SUCCESS = 0
ERROR   = 1

# --------------------------------------------------------------------------------------------------------------

def printerror(sMsg):
    sys.stderr.write(COLBR + f"Error: {sMsg}!\n")

def printexception(sMsg):
    sys.stderr.write(COLBR + f"Exception: {sMsg}!\n")

# --------------------------------------------------------------------------------------------------------------

class ExtendedInstallCommand(install):
    """Extended setup for installation mode."""

    def run(self):

        listCmdArgs = sys.argv
        if ( ('install' in listCmdArgs) or ('build' in listCmdArgs) or ('sdist' in listCmdArgs) or ('bdist_wheel' in listCmdArgs) ):
            install.run(self)
        return SUCCESS

# eof class ExtendedInstallCommand(install):

# --------------------------------------------------------------------------------------------------------------

# -- setting up the repository configuration
oRepositoryConfig = None
try:
    oRepositoryConfig = CRepositoryConfig(os.path.abspath(sys.argv[0]))
except Exception as ex:
    print()
    printexception(str(ex))
    print()
    sys.exit(ERROR)

# -- setting up the extended setup
oExtendedSetup = None
try:
    oExtendedSetup = CExtendedSetup(oRepositoryConfig)
except Exception as ex:
    print()
    printexception(str(ex))
    print()
    sys.exit(ERROR)

# --------------------------------------------------------------------------------------------------------------

long_description = "long description"

listCmdArgs = sys.argv
if ( ('install' in listCmdArgs) or ('build' in listCmdArgs) or ('sdist' in listCmdArgs) or ('bdist_wheel' in listCmdArgs) ):
    print()
    print(COLBY + "Entering extended installation")
    print()

    print(COLBY + "Extended setup step 1/5: Calling the documentation builder")
    print()

    nReturn = oExtendedSetup.genpackagedoc()
    if nReturn != SUCCESS:
        sys.exit(nReturn)

    print(COLBY + "Extended setup step 2/5: Converting the repository README")
    print()

    nReturn = oExtendedSetup.convert_repo_readme()
    if nReturn != SUCCESS:
        sys.exit(nReturn)

    print(COLBY + "Extended setup step 3/5: Deleting previous setup outputs (build, dist, <package name>.egg-info within repository)")
    print()
    nReturn = oExtendedSetup.delete_previous_build()
    if nReturn != SUCCESS:
        sys.exit(nReturn)

    if ( ('bdist_wheel' in listCmdArgs) or ('build' in listCmdArgs) ):
        print()
        print(COLBY + "Skipping extended setup step 4/5: Deleting previous package installation folder within site-packages")
        print()
    else:
        print()
        print(COLBY + "Extended setup step 4/5: Deleting previous package installation folder within site-packages")
        print()
        nReturn = oExtendedSetup.delete_previous_installation()
        if nReturn != SUCCESS:
            sys.exit(nReturn)

    README_MD = str(oRepositoryConfig.Get('README_MD'))
    if os.path.isfile(README_MD):
        with open(README_MD, "r", encoding="utf-8") as fh:
            long_description = fh.read()
        fh.close()
    else:
        long_description = str(oRepositoryConfig.Get('DESCRIPTION'))

# --------------------------------------------------------------------------------------------------------------

# -- the 'setup' itself

print(COLBY + "Extended setup step 5/5: install.run(self)")
print()

setuptools.setup(
    name         = str(oRepositoryConfig.Get('PACKAGENAME')),
    version      = str(oRepositoryConfig.Get('PACKAGEVERSION')),
    author       = str(oRepositoryConfig.Get('AUTHOR')),
    author_email = str(oRepositoryConfig.Get('AUTHOREMAIL')),
    description  = str(oRepositoryConfig.Get('DESCRIPTION')),
    long_description = long_description,
    long_description_content_type = str(oRepositoryConfig.Get('LONGDESCRIPTIONCONTENTTYPE')),
    url = str(oRepositoryConfig.Get('URL')),
    packages = [str(oRepositoryConfig.Get('PACKAGENAME')),
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".config",
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".core",
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".logging",
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".process",
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".process.platform",
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".runtime",
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".transport",
                str(oRepositoryConfig.Get('PACKAGENAME')) + ".ui"],
    include_package_data=True,
    classifiers = [
        str(oRepositoryConfig.Get('PROGRAMMINGLANGUAGE')),
        str(oRepositoryConfig.Get('LICENCE')),
        str(oRepositoryConfig.Get('OPERATINGSYSTEM')),
        str(oRepositoryConfig.Get('DEVELOPMENTSTATUS')),
        str(oRepositoryConfig.Get('INTENDEDAUDIENCE')),
        str(oRepositoryConfig.Get('TOPIC')),
    ],
    python_requires = str(oRepositoryConfig.Get('PYTHONREQUIRES')),
    cmdclass={
        'install': ExtendedInstallCommand,
    },
    install_requires = oRepositoryConfig.Get('INSTALLREQUIRES'),
    package_data={f"{oRepositoryConfig.Get('PACKAGENAME')}" : oRepositoryConfig.Get('PACKAGEDATA')},
)
# --------------------------------------------------------------------------------------------------------------

print()
print(COLBG + "Extended installation done")
print()

# --------------------------------------------------------------------------------------------------------------
