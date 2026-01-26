#!/usr/bin/env python3

###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 31. Jan. 2024
#

__version__ = "1.1.1"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import socket, time, logging, threading, asyncio, struct, copy, re
from utilities import DEFAULT, VM_NIC_control, netns
from utilities.icmplib import async_multiping

##########################################################################
REGEX_IP = re.compile(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")

log = logging.getLogger('vFAD')

##########################################################################
class prep(threading.Thread):
    '''VM processor'''

    ######################################################################
    def run(self) -> None:
        log.debug("VM-%s %s (%s) is starting" % (self._kwargs['id'],prep.__doc__,__version__))
        self.id         = threading.current_thread().name
        self.vlanId     = self._kwargs['id']
        self.config     = self._kwargs['config']
        self.nic        = self._kwargs['nic']
        self.newConfig  = False
        self.stats      = self._kwargs['stats'].copy()
        self.newState   = False
        self.running    = True
        self.lock       = threading.Lock()
        self.pingTargets= list()
        self.pingDelay  = self._kwargs['stats'].copy()
        self.mcastExpire= 0
        self.mcastClient= 0
        self.issue      = False
        
        try:
            VM_NIC_control.commition(self.nic,self.vlanId,self.config)
        except Exception as eMsg:
            log.warning("NIC commition failed: '%s'" % eMsg)
        
        if self.config['dhcp']:
            self._checkDhcpIp()
        
        if self.config['ip']:
            if self.running:
                self._setupPing()
                self._setupMcastServer()
                self._setupMcastClient()
                self._setupIperf()
                self._setupWeb()
                self.newState = True

                asyncio.run(self._mainLoop())
                if self.config['iperf']: VM_NIC_control.iperfKill(self.vlanId)
                if self.config['web']:   VM_NIC_control.webKill(self.vlanId)
        else:
            log.info("%s stop working, no IP address given" % self.id)
            VM_NIC_control.decommition(self.vlanId)
            return
        
        if self.config['dhcp']:
            VM_NIC_control.dhcpKill(self.vlanId)
        VM_NIC_control.decommition(self.vlanId)
        log.debug("%s stoped" % self.id)

    ######################################################################
    async def _mainLoop(self) -> None:
        checkDgw = DEFAULT.VM_DGW_CHECK
        log.debug("%s enter run loop" % self.id)
        while self.running:
            start = time.time()
            tasks = dict()
            if self.pingTargets:
                tasks['ping'] = asyncio.create_task(async_multiping(self.pingTargets,count=1,timeout=0.15,netnsName=self.id))
            if self.config['mcast']['server']:
                tasks['mcastServer'] = asyncio.create_task(self._runMcastServer())
            if self.config['mcast']['client']:
                tasks['mcastClient'] = asyncio.create_task(self._runMcastClient())
            
            if not self.running: break

            if self.pingTargets:
                pingResult = await tasks['ping']
                self._pingCheck(pingResult)
            if self.config['mcast']['server']:
                await tasks['mcastServer']
            if self.config['mcast']['client']:
                await tasks['mcastClient']
                self.stats['mcast']['client'] = self.mcastClient

            if not self.running: break

            if not checkDgw:
                VM_NIC_control.checkDgw(self.vlanId,self.config)
                checkDgw = DEFAULT.VM_DGW_CHECK
            else:
                checkDgw -= 1
            
            if not self.running: break
            
            wait = DEFAULT.VM_CYCLE - (time.time()-start)
            if wait > 0: time.sleep(wait)

    ######################################################################
    def _checkDhcpIp(self) -> None:
        if self.config['dhcp']:
            log.debug("%s send DHCP request" % self.id)
            while self.running:
                expireTime = time.time() + 70
                try:
                    VM_NIC_control.dhcpAquire(self.vlanId)
                except Exception as eMsg:
                    log.warning("DHCP request failed: '%s'" % eMsg)
                while expireTime > time.time() and self.running:
                    time.sleep(0.1)
                    try:
                        ipInfo = VM_NIC_control.status(self.vlanId)
                    except Exception as eMsg:
                        log.warning("get DHCP status failed: '%s'" % eMsg)
                        continue
                    if ipInfo['ip']:
                        with self.lock:
                            self.config['ip'] = ipInfo['ip']
                            log.debug("%s got DHCP IP %s" % (self.id,ipInfo['ip']))
                            if ipInfo['dgw']:
                                self.config['dgw'] = ipInfo['dgw']
                                log.debug("%s got DHCP default GW %s" % (self.id,ipInfo['dgw']))
                            self.newConfig = True
                        time.sleep(0.1)
                        return
                if self.running:
                    #log.debug("%s reach DHCP timeout, retrigger new DHCP request" % self.id)
                    try:
                        VM_NIC_control.dhcpKill(self.vlanId)
                    except Exception as eMsg:
                        log.warning("DHCP kill failed: '%s'" % eMsg)
                else:
                    VM_NIC_control.decommition(self.vlanId)
                    return

    ######################################################################
    def _setupPing(self) -> None:
        if not self.running: return
        with self.lock:
            for ip in self.config['ping']:
                if ip == '': continue
                match = REGEX_IP.search(ip)
                if match:
                    self.stats['ping'][ip] = 0
                    self.pingTargets.append(ip)
                else:
                    log.warning("%s ping targets '%s' is not a valide IP address" % (self.id,ip))
            if self.config['dgw']:
                match = REGEX_IP.search(self.config['dgw'])
                if match:
                    self.stats['ping'][self.config['dgw']] = 0
                    self.pingTargets.append(self.config['dgw'])
                else:
                    log.warning("%s DGW ping targets '%s' is not a valide IP address" % (self.id,self.config['dgw']))
            self.newState = True
            if self.pingTargets:
                log.debug("%s ping targets are %s" % (self.id,self.pingTargets))
        
    ######################################################################
    def _pingCheck(self, pingResult) -> None:
        for host in pingResult:
            if not host.address in self.stats['ping']: continue
            if host.is_alive:
                if self.config['dgw'] == host.address:
                    if self.pingDelay['dgw'] != 1:
                        self.pingDelay['dgw'] = 1
                        with self.lock:
                            self.newState = True
                            self.stats['dgw'] = 1
                            self.stats['ping'][host.address] = 1
                        log.debug("%s DGW %s is up" % (self.id,host.address))
                elif self.stats['ping'][host.address] != 1:
                    if self.pingDelay['ping'][host.address] != 1:
                        self.pingDelay['ping'][host.address] = 1
                        with self.lock:
                            self.newState = True
                            self.stats['ping'][host.address] = 1
                        log.debug("%s PING %s is up" % (self.id,host.address))
            else:
                if self.config['dgw'] == host.address:
                    if self.pingDelay['dgw'] != 2:
                        self.pingDelay['dgw'] = 2
                        with self.lock:
                            self.newState = True
                            self.stats['dgw'] = 2
                            self.pingDelay['ping'][host.address] = 2
                        log.debug("%s DGW %s is down" % (self.id,host.address))
                elif self.stats['ping'][host.address] != 2:
                    if self.pingDelay['ping'][host.address] != 2:
                        self.pingDelay['ping'][host.address] = 2
                        with self.lock:
                            self.newState = True
                            self.stats['ping'][host.address] = 2
                        log.debug("%s PING %s is down" % (self.id,host.address))

    ######################################################################
    def _setupMcastServer(self) -> None:
        if not self.running: return
        with self.lock:
            if self.config['mcast']['server']:
                self.mcastSrvGroup, self.mcastSrvPort = self.config['mcast']['server'].split(':')
                self.mcastSrvPort = int(self.mcastSrvPort)
                with netns.NetNS(nsname=self.id):
                    self.mcastSrvSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                    self.mcastSrvSocket.setsockopt(socket.IPPROTO_IP,socket.IP_MULTICAST_TTL,DEFAULT.MCAST_TTL)
                self.stats['mcast']['server'] = 1
                log.debug("%s MCAST server %s is prepared" % (self.id,self.config['mcast']['server']))
            else:
                self.stats['mcast']['server'] = 0
                log.debug("%s MCAST server unused, no job" % self.id)
            self.mcastSendCounter = 0

    ######################################################################
    async def _runMcastServer(self) -> None:
        self.mcastSendCounter += 1
        try:
            self.mcastSrvSocket.sendto(bytes('VM-%s send packet %s' % (self.id,self.mcastSendCounter), 'UTF-8'), (self.mcastSrvGroup,self.mcastSrvPort))
            if self.issue:
                log.info("VM-%s start sending mcast frame" % self.id,)
                self.issue = False
                self.newState = True
        except Exception as errorMsg:
            if not self.issue:
                log.warning("VM-%s send mcast frame failed, '%s'" % (self.id,errorMsg))
                self.issue = True

    ######################################################################
    def _setupMcastClient(self) -> None:
        if not self.running: return
        with self.lock:
            if self.config['mcast']['client']:
                self.mcastClientGroup, self.mcastClientPort = self.config['mcast']['client'].split(':')
                self.mcastClientPort = int(self.mcastClientPort)
                with netns.NetNS(nsname=self.id):
                    self.mcastClientSocket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM,socket.IPPROTO_UDP)
                    self.mcastClientSocket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1)
                    self.mcastClientSocket.bind((self.mcastClientGroup,self.mcastClientPort))
                    # for IGMP
                    mcastRequest = struct.pack('4s4s',socket.inet_aton(self.mcastClientGroup),socket.inet_aton(self.config['ip'].split('/')[0]))
                    self.mcastClientSocket.setsockopt(socket.IPPROTO_IP,socket.IP_ADD_MEMBERSHIP, mcastRequest)
                    self.mcastClientSocket.setblocking(0)
                log.debug("%s MCAST client %s is prepared" % (self.id,self.config['mcast']['client']))
            else:
                log.debug("%s MCAST client unused, no job" % self.id)
            self.stats['mcast']['client'] = 0

    ######################################################################
    async def _runMcastClient(self) -> None:
        try:
            with netns.NetNS(nsname=self.id):
                self.mcastClientSocket.recv(256)

            if not self.mcastClient == 1:
                with self.lock:
                    self.newState = True
                    self.mcastClient = 1
                log.debug("%s MCAST client %s recive data" % (self.id,self.config['mcast']['client']))
                self.mcastExpire = time.time() + 2
        except:
            if not self.mcastClient == 2:
                if self.mcastExpire < time.time():
                    with self.lock:
                        self.newState = True
                        self.mcastClient = 2
                    log.debug("%s MCAST client %s recive no data" % (self.id,self.config['mcast']['client']))
    
    ######################################################################
    def _setupIperf(self) -> None:
        if self.config['iperf']:
            try:
                VM_NIC_control.iperfSetup(self.vlanId)
                self.stats['iperf'] = True
                log.debug("%s IPerf server is prepared" % self.id)
            except Exception as eMsg:
                log.warning("IPerf setup failed: '%s'" % eMsg)
        else:
            self.stats['iperf'] = False
            log.debug("%s IPerf server unused, no job" % self.id)

    ######################################################################
    def _setupWeb(self) -> None:
        if self.config['web']:
            try:
                VM_NIC_control.webSetup(self.vlanId)
                self.stats['web'] = True
                log.debug("%s WEB server is prepared" % self.id)
            except Exception as eMsg:
                log.warning("WEB server setup failed: '%s'" % eMsg)
        else:
            self.stats['web'] = False
            log.debug("%s WEB server unused, no job" % self.id)
        
    ######################################################################
    def getConfig(self) -> None:
        with self.lock:
            buffer = copy.deepcopy(self.config)
            self.newConfig = False
        return buffer
    
    ######################################################################
    def getStats(self) -> None:
        with self.lock:
            buffer = copy.deepcopy(self.stats)
            self.newState = False
        return buffer

######################################################################
