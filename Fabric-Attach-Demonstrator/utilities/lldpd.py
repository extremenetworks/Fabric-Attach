###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 26. Oct. 2023
#            updated 19.05.2025

__version__ = "1.0.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import time,json,copy,logging,sys,platform
from fcntl import ioctl
from ctypes import c_char,c_short,Structure
from socket import socket,htons,AF_PACKET,SOCK_RAW
from utilities import DEFAULT,lldp_decode,lldp_encode,VM_NIC_control,common

######################################################################
LLDP_DST_MAC  = bytes.fromhex(DEFAULT.LLDP_DST_MAC)
LLDP_PROTOCOL = bytes.fromhex(DEFAULT.LLDP_PROTOCOL_ID)

log           = logging.getLogger('vFAD')

######################################################################
class ifreq(Structure):
    _fields_ = [ ("ifr_ifrn", c_char * 16),("ifr_flags", c_short) ]

#####################################################################################################
class init():
    '''LLDP daemon'''
    ######################################################################
    def __init__(self,nic: dict, newConfig: dict = DEFAULT.INIT_CONFIG) -> object:
        log.debug("%s (%s) is starting" % (init.__doc__,__version__))
        self.newInData  = False
        self.newOutData = False
        self.nicError   = False
        self.nic        = nic
        self.os         = dict()
        self.config     = copy.deepcopy(DEFAULT.INIT_CONFIG)
        self.session    = dict()
        self.sock       = socket(AF_PACKET,SOCK_RAW,htons(DEFAULT.ETH_P_ALL))
        self.sock.setblocking(False)

        self._determinateOs()

        try:
            self.sock.bind((self.nic['name'],0))
            #log.debug("bind socket on NIC '%s'" % self.nic['name'])
        except Exception as e:
            log.error("unable to bind socket on NIC '%s'" % self.nic['name'])
            raise ValueError("unable to bind socket NIC '%s'" % self.nic['name'])
        
        VM_NIC_control.bringUpNic(self.nic['name'])

        self._promiscuous_mode(self.nic['name'],self.sock,True)
        self.loadConfig(newConfig)

   ######################################################################
    def __repr__(self) -> dict:
        return '%s' % self.__dict__
        
    ######################################################################
    def __del__(self) -> None:
        pass

    ######################################################################
    def _determinateOs(self):
        if sys.maxsize - 2**64/2 == 0.0:
            self.os['bitLength'] = 64
        elif sys.maxsize - 2**32/2 == 0.0:
            self.os['bitLength'] = 32
        else:
            log.error("unknown OS bit length: "+ sys.maxsize)
            self.os['bitLength'] = 0

        architecture = platform.machine()
        if "arch" in architecture.lower():
            log.info("CPU is ARM based, %s bit" % self.os['bitLength'])
            self.os['hwType'] = 'AArch'
        elif "x86" in architecture.lower() or "amd64" in architecture.lower():
            log.debug("CPU is Intel/AMD based, %s bit" % self.os['bitLength'])
            self.os['hwType'] = 'amd'
        else:
            log.error("unknown CPU architecture: "+ architecture)
            self.os['hwType'] = 'unknown'
        
    ######################################################################
    def loadConfig(self,newConfig: dict) -> None:
        self.config = copy.deepcopy(newConfig)
        if not 'name'        in self.config['LLDP']:
            self.config['LLDP']['name'] = DEFAULT.LLDP_CONFIG['sysName']
        if not 'description' in self.config['LLDP']:
            self.config['LLDP']['description'] = DEFAULT.LLDP_CONFIG['sysDesc']
        self.session['receive'] = lldp_decode.init(self.os,self.config['LLDP']['FA-Element'])
        self.session['send']    = lldp_encode.init(self.os,nic=self.nic,lldpSet=self.config['LLDP'])
        self.session['send'].updateFaAssignment(self.config)
        
        sendData = self.session['receive'].decode(self.session['send'].lldpFrame[14:],False)
        
        if not self.config['LLDP']['FA-Element']['secret'] == '':
            sendData['FA-Element']['secret'] = self.config['LLDP']['FA-Element']['secret']
        if sendData:
            if 'expire' in sendData:
                del sendData['expire']
            log.debug("send LLDP via NIC %s:\n%s\n" % (self.nic['name'],json.dumps(sendData,indent=2,sort_keys=True)))
            self.session['send'].nextSend = 0
            self.newOutData = sendData
        else:
            log.error("!!! send LLDP data integrity check failed !!!\n%s" % json.dumps(self.config,indent=2,sort_keys=True))

    ######################################################################
    def _promiscuous_mode(self,interface: str,sock: object,enable: bool = False) -> None:
        SIOCGIFFLAGS = 0x8913
        SIOCSIFFLAGS = 0x8914
        IFF_PROMISC  = 0x100
        ifr          = ifreq()
        ifr.ifr_ifrn = bytes(interface, 'utf-8')
        ioctl(sock.fileno(), SIOCGIFFLAGS, ifr)
        if enable:
            ifr.ifr_flags |= IFF_PROMISC
        else:
            ifr.ifr_flags &= ~IFF_PROMISC
        ioctl(sock.fileno(), SIOCSIFFLAGS, ifr)

    ######################################################################
    def run(self) -> None:
        if self.session['send'].nextSend <= time.time():
            try:
                self.sock.send(self.session['send'].lldpFrame)
                if self.nicError:
                    log.debug("start sending LLDP frames")
                    self.nicError = False
                    self.newInData = True
            except Exception as errorMsg:
                if not self.nicError:
                    if common.ifDebugLog():
                        log.warning("send LLDP frame via NIC %s failed: '%s'" % (self.nic['name'], errorMsg))
                    self.nicError = True
            finally:
                self.session['send'].nextSend = time.time() + DEFAULT.LLDP_UPDATE
        
        if 'expire' in self.session['receive'].data:
            if self.session['receive'].data['expire'] < time.time():
                log.debug("LLDP neigbor expired, %0.3f sec" % (time.time() - self.session['receive'].data['expire']))
                self.session['receive'].clearData()
                self.newInData = True
        
        try:
            packet = self.sock.recvfrom(9000)
        except:
            return

        if LLDP_DST_MAC == packet[0][0:6] and LLDP_PROTOCOL == packet[0][12:14]:
            if self.session['receive'].decode(packet[0][14:]):
                log.debug("received LLDP via NIC %s:\n%s\n" % (
                    self.nic['name'],
                    json.dumps(self.session['receive'].data,indent=2,sort_keys=True)
                ))
                self.newInData = True
            else:
                if self.session['receive'].errorMsg():
                    log.warning("received LLDP via NIC %s failed to decode: %s" % (
                        self.nic['name'],
                        self.session['receive'].errorMsg()
                    ))

    ######################################################################
    def newData(self,direction: str) -> dict:
        if direction == 'in':
            return self.newInData
        elif direction == 'out':
            return self.newOutData
        
    ######################################################################
    def getData(self,direction: str) -> dict:
        if direction == 'in':
            data = copy.deepcopy(self.session['receive'].data)
            self.newInData = False
            return data
        elif direction == 'out':
            data = self.newOutData
            self.newOutData = False
            return data
    
######################################################################
