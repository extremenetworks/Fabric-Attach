###########################################################################
# source https://github.com/larsks/python-netns
# copy by Markus Nikulski
#         markus@nikulski.net
#         created 31. Jan. 2024
#

__version__ = "1.0.0"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import os
import socket as socket_module
from ctypes import CDLL, get_errno

######################################################################
#CLONE_NEWIPC = 0x08000000
CLONE_NEWNET = 0x40000000
#CLONE_NEWUTS = 0x04000000

######################################################################
def socket(nspath, *args):
    with NetNS(nspath=nspath):
        return socket_module.socket(*args)

######################################################################
class NetNS (object):
    def __init__(self, nsname=None, nspath=None, nspid=None):
        self.libc = CDLL('libc.so.6', use_errno=True)
        self.libc.setns.errcheck = self._errcheck

        self.mypath = self._get_ns_path(nspid=os.getpid())
        self.targetpath = self._get_ns_path(nspath,nsname=nsname,nspid=nspid)
        if not self.targetpath:
            raise ValueError('invalid namespace')

    ##################################################################
    def __enter__(self):
        self.myns = open(self.mypath)
        with open(self.targetpath) as fd:
            self._setns(fd, CLONE_NEWNET)

    ##################################################################
    def __exit__(self, *args):
        self._setns(self.myns, CLONE_NEWNET)
        self.myns.close()

    ##################################################################
    def _errcheck(self, ret, func, args):
        if ret == -1:
            e = get_errno()
            raise OSError(e, os.strerror(e))
    
    ##################################################################
    def _get_ns_path(self, nspath=None, nsname=None, nspid=None):
        if nsname:
            nspath = '/var/run/netns/%s' % nsname
        elif nspid:
            nspath = '/proc/%d/ns/net' % nspid

        if not os.path.exists(nspath):
            raise ValueError('namespace path %s does not exist' % nspath)
        return nspath
    
    ##################################################################
    def _setns(self, fd, nstype):
        if hasattr(fd, 'fileno'):
            fd = fd.fileno()
        return self.libc.setns(fd, nstype)

######################################################################
