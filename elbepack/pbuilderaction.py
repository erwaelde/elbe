#!/usr/bin/env python
#
# ELBE - Debian Based Embedded Rootfilesystem Builder
# Copyright (C) 2013  Linutronix GmbH
#
# This file is part of ELBE.
#
# ELBE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ELBE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ELBE.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function

import elbepack
from elbepack.treeutils   import etree
from elbepack.directories import elbe_exe
from elbepack.shellhelper import CommandError, system, command_out_stderr
from elbepack.filesystem  import wdfs, TmpdirFilesystem, Filesystem
from elbepack.elbexml     import ElbeXML, ValidationError

import sys

import os
import datetime

cmd_exists = lambda x: any(os.access(os.path.join(path, x), os.X_OK) for path in os.environ["PATH"].split(os.pathsep))

# Create download directory with timestamp,
# if necessary
def ensure_outdir (wdfs, opt):
    if opt.outdir is None:
        opt.outdir = ".."

    print ("Saving generated Files to %s" % opt.outdir)

class PBuilderError(Exception):
    def __init__(self, str):
        Exception.__init__(self, str)

class PBuilderAction(object):
    actiondict = {}
    @classmethod
    def register(cls, action):
        cls.actiondict[action.tag] = action
    @classmethod
    def print_actions(cls):
        print ('available subcommands are:', file=sys.stderr)
        for a in cls.actiondict:
            print ('   ' + a, file=sys.stderr)
    def __new__(cls, node):
        action = cls.actiondict[node]
        return object.__new__(action, node)
    def __init__(self, node):
        self.node = node

class CreateAction(PBuilderAction):

    tag = 'create'

    def __init__(self, node):
        PBuilderAction.__init__(self, node)

    def execute(self, opt, args):
        tmp = TmpdirFilesystem ()

        if not opt.project:
            print ('you need to specify --project option', file=sys.stderr)
            sys.exit(20)

        prjdir = opt.project

        print ("Creating pbuilder")

        try:
            system ('%s control build_pbuilder "%s"' % (elbe_exe, prjdir))
        except CommandError:
            print ("elbe control build_pbuilder Failed", file=sys.stderr)
            print ("Giving up", file=sys.stderr)
            sys.exit(20)

        try:
            system ('%s control wait_busy "%s"' % (elbe_exe, prjdir) )
        except CommandError:
            print ("elbe control wait_busy Failed", file=sys.stderr)
            print ("Giving up", file=sys.stderr)
            sys.exit(20)

        print ("")
        print ("Building Pbuilder finished !")
        print ("")

PBuilderAction.register(CreateAction)

class BuildAction(PBuilderAction):

    tag = 'build'

    def __init__(self, node):
        PBuilderAction.__init__(self, node)

    def execute(self, opt, args):
        tmp = TmpdirFilesystem ()

        if opt.xmlfile:
            ret, prjdir, err = command_out_stderr ('%s control create_project --retries 60 "%s"' % (elbe_exe, opt.xmlfile))
            if ret != 0:
                print ("elbe control create_project failed.", file=sys.stderr)
                print (err, file=sys.stderr)
                print ("Giving up", file=sys.stderr)
                sys.exit(20)

            prjdir = prjdir.strip()

            try:
                system ('%s control build "%s"' % (elbe_exe, prjdir) )
            except CommandError:
                print ("elbe control build Failed", file=sys.stderr)
                print ("Giving up", file=sys.stderr)
                sys.exit(20)

            print ("Build started, waiting till it finishes")

            try:
                system ('%s control wait_busy "%s"' % (elbe_exe, prjdir) )
            except CommandError:
                print ("elbe control wait_busy Failed", file=sys.stderr)
                print ("Giving up", file=sys.stderr)
                sys.exit(20)

            print ("")
            print ("Build finished !")
            print ("")
            print ("Creating pbuilder")

            try:
                system ('%s control build_pbuilder "%s"' % (elbe_exe, prjdir))
            except CommandError:
                print ("elbe control build_pbuilder Failed", file=sys.stderr)
                print ("Giving up", file=sys.stderr)
                sys.exit(20)

            try:
                system ('%s control wait_busy "%s"' % (elbe_exe, prjdir) )
            except CommandError:
                print ("elbe control wait_busy Failed", file=sys.stderr)
                print ("Giving up", file=sys.stderr)
                sys.exit(20)

            print ("")
            print ("Building Pbuilder finished !")
            print ("")
        elif opt.project:
            prjdir = opt.project
        else:
            print ('you need to specify --project or --xmlfile option', file=sys.stderr)
            sys.exit(20)

        print ("")
        print ("Packing Source into tmp archive")
        print ("")
        try:
            system ('tar cvfz "%s" .' % (tmp.fname ("pdebuild.tar.gz")))
        except CommandError:
            print ("tar Failed", file=sys.stderr)
            print ("Giving up", file=sys.stderr)
            sys.exit(20)

        print ("")
        print ("Pushing source into pbuilder")
        print ("")

        try:
            system ('%s control set_pdebuild "%s" "%s"' % (elbe_exe, prjdir, tmp.fname ("pdebuild.tar.gz")))
        except CommandError:
            print ("elbe control set_pdebuild Failed", file=sys.stderr)
            print ("Giving up", file=sys.stderr)
            sys.exit(20)
        try:
            system ('%s control wait_busy "%s"' % (elbe_exe, prjdir) )
        except CommandError:
            print ("elbe control wait_busy Failed", file=sys.stderr)
            print ("Giving up", file=sys.stderr)
            sys.exit(20)
        print ("")
        print ("Pdebuild finished !")
        print ("")

        if opt.skip_download:
            print ("")
            print ("Listing available files:")
            print ("")
            try:
                system ('%s control --pbuilder-only get_files "%s"' % (elbe_exe, prjdir) )
            except CommandError:
                print ("elbe control get_files Failed", file=sys.stderr)
                print ("", file=sys.stderr)
                print ("dumping logfile", file=sys.stderr)

                try:
                    system ('%s control dump_file "%s" log.txt' % (
                            elbe_exe, prjdir ))
                except CommandError:
                    print ("elbe control dump_file Failed", file=sys.stderr)
                    print ("", file=sys.stderr)
                    print ("Giving up", file=sys.stderr)

                sys.exit(20)

            print ("")
            print ('Get Files with: elbe control get_file "%s" <filename>' % prjdir)
        else:
            print ("")
            print ("Getting generated Files")
            print ("")

            ensure_outdir (wdfs, opt)

            try:
                system ('%s control --pbuilder-only get_files --output "%s" "%s"' % (
                        elbe_exe, opt.outdir, prjdir ))
            except CommandError:
                print ("elbe control get_files Failed", file=sys.stderr)
                print ("", file=sys.stderr)
                print ("dumping logfile", file=sys.stderr)

                try:
                    system ('%s control dump_file "%s" log.txt' % (
                            elbe_exe, prjdir ))
                except CommandError:
                    print ("elbe control dump_file Failed", file=sys.stderr)
                    print ("", file=sys.stderr)
                    print ("Giving up", file=sys.stderr)

                sys.exit(20)

PBuilderAction.register(BuildAction)

