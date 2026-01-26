###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 29. Jan. 2024
#

# apt install python3-deepdiff

__version__ = "1.0.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import time, logging, copy, json
from utilities import DEFAULT, VM_processor

##########################################################################
log     = logging.getLogger('vFAD')
config  = copy.deepcopy(DEFAULT.INIT_CONFIG)

##########################################################################
class init():
    '''VM-Dealer daemon'''
    ######################################################################
    def __init__(self,nic: dict, config: dict = DEFAULT.INIT_CONFIG['VM']) -> object:
        log.debug("%s (%s) is starting" % (init.__doc__,__version__))
        self.newConfig= False
        self.vmConfig = dict()
        self.newStats = False
        self.stats    = dict()
        self.config   = copy.deepcopy(config)
        self.nic      = nic
        self.vm       = dict()

        for vmId in self.config:
            self.setupVm(vmId)

    ######################################################################
    def loadConfig(self,newConfig: dict) -> None:
        vms = {'add': list(), 'update': list(), 'delete': list()}
        
        for vmId in self.config:
            if vmId in newConfig:
                curCfgString = copy.deepcopy(self.config[vmId])
                if curCfgString['dhcp']:
                    curCfgString['ip']  = ''
                    curCfgString['dgw'] = ''
                if not json.dumps(newConfig[vmId],sort_keys=True) == json.dumps(curCfgString,sort_keys=True):
                    vms['update'].append(vmId)
                    log.debug("VM-Dealer force update 'VM-%s'" % vmId)
            else:
                vms['delete'].append(vmId)
                log.debug("VM-Dealer force delete 'VM-%s'" % vmId)
        
        for vmId in newConfig:
            if not vmId in self.config:
                vms['add'].append(vmId)
                log.debug("VM-Dealer force add 'VM-%s'" % vmId)

        for vmId in vms['delete']:
            self.trashVm(vmId)
        
        for vmId in vms['update']:
            self.trashVm(vmId)
            self.config[vmId] = copy.deepcopy(newConfig[vmId])
            self.setupVm(vmId)
            
        for vmId in vms['add']:
            self.config[vmId] = copy.deepcopy(newConfig[vmId])
            self.setupVm(vmId)

    ######################################################################
    def setupVm(self, vmId) -> None:
        log.debug("VM-Dealer setup 'VM-%s'" % vmId)
        self.stats[vmId] = DEFAULT.VM_STATS
        
        self.stats[vmId]['ping'] = dict()
        for ip in self.config[vmId]['ping']:
            self.stats[vmId]['ping'][ip] = 0
        
        self.vm[vmId] = VM_processor.prep(
            name    = "VM-%s" % vmId,
            kwargs  = {
                'id': vmId,
                'config': self.config[vmId],
                'stats':  self.stats[vmId],
                'nic': self.nic
            }
        )
        self.vm[vmId].start()
        time.sleep(0.01)

    ######################################################################
    def trashVm(self, vmId) -> None:
        log.debug("VM-Dealer trash 'VM-%s'" % vmId)
        self.vm[vmId].running = False
        self.vm[vmId].join()
        del self.vm[vmId]
        if vmId in self.config: del self.config[vmId]
        if vmId in self.stats:  del self.stats[vmId]

    ######################################################################
    def run(self) -> None:
        for vmId in self.config:
            try:
                if self.vm[vmId].newConfig:
                    self.vmConfig[vmId] = copy.deepcopy(self.vm[vmId].getConfig())
                    self.newConfig = True
                if self.vm[vmId].newState:
                    self.stats[vmId] = self.vm[vmId].getStats()
                    self.newStats = True
            except Exception as e:
                log.error("run check failed for vmId %s: '%s'" % (vmId,e))

    ######################################################################
    def getConfig(self) -> dict:
        data = dict()
        for vmId in self.vmConfig:
            data[vmId] = dict()
            data[vmId]['ip']  = self.vmConfig[vmId]['ip']
            data[vmId]['dgw'] = self.vmConfig[vmId]['dgw']
        self.newConfig = False
        self.vmConfig = dict()
        return data
    
    ######################################################################
    def getStatus(self) -> dict:
        buffer = copy.deepcopy(self.stats)
        self.newStats = False
        self.stats = dict()
        return buffer
    
    ######################################################################
    def exitHandler(self) -> None:
        vmIds = list()
        for vmId in self.config: vmIds.append(vmId)
        for vmId in vmIds: self.trashVm(vmId)
        log.debug('VM-Dealer stoped')

##########################################################################
