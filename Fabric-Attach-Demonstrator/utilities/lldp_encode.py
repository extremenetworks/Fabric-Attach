###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 26. Oct. 2023
#            updated 19.05.2025

# https://www.rapidtables.com/convert/number/hex-to-decimal.html

__version__ = "1.0.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import logging, ctypes, os, os.path, subprocess, hashlib, hmac
from socket import inet_aton
from utilities import DEFAULT

#####################################################################################################
log = logging.getLogger('vFAD')

#####################################################################################################
class init():
    '''LLDP send interface'''
    
    ######################################################################
    def __init__(self, osInfo: dict, nic: str, lldpSet: dict) -> object:
        log.debug("%s (%s) is starting" % (init.__doc__,__version__))
        self.osInfo     = osInfo
        self.nic        = nic
        self.devType    = lldpSet['devType']
        self.msgAuth    = lldpSet['FA-Element']['msgAuth']
        self.secret     = lldpSet['FA-Element']['secret'].encode("UTF-8")
        self.sysName    = lldpSet['name']
        self.sysDesc    = lldpSet['description']
        self.header     = b''                               # just the LLDP except the FA part
        self.lldpFrame  = b''                               # the entire LLDP frame
        self.nextSend   = 0
        
        self.nic['MAC'] = self.nic['MAC'].replace(':','')
        self.systemId   = self.nic['MAC'] +"00000001"

        self._loadHashLibrary()
        self._lldpHeader()

    ######################################################################
    def __repr__(self):
        return '%s' % self.__dict__
        
    ######################################################################
    def __del__(self):
        pass
    
    ######################################################################
    def _loadHashLibrary(self):
        fileName = os.getcwd() +'/utilities/hmac_sha-256_%s_%s.so' % (self.osInfo['hwType'],self.osInfo['bitLength'])
        if os.path.isfile(fileName):
            try:
                self.hmacSha256 = ctypes.cdll.LoadLibrary(fileName)
                #log.debug("cHASH library in place")
                process = subprocess.Popen(os.getcwd() +"/utilities/hmacSha256.py", shell=True)
                process.wait()
                if process.returncode == 0:
                    # log.debug("cHASH library test passed")
                    return
                else:
                    log.warning("cHASH library test failed [%s]" % process.returncode)
            except Exception as e:
                log.warning("cHASH library loading failed: '%s'" % e)
        else:
            log.info("cHASH library is missing")
        
        self.hmacSha256 = False

    ######################################################################
    def _packLldpCapabilities(self) -> str:
        if self.devType in DEFAULT.LLDP_DEVICE_TYPES:
            capabilities = DEFAULT.LLDP_DEVICE_TYPES[self.devType]['LLDP']
        else:
            log.warning("LLDP device type '%s' unknow, take 'OVS'" % self.devType)
            capabilities = DEFAULT.LLDP_DEVICE_TYPES['OVS']['LLDP']
        capBitMask = 0
        for capability in capabilities:
            count = 1
            for item in DEFAULT.LLDP_CAPABILITY_MAP:
                if capability == item:
                    capBitMask += count
                    break
                count *= 2
        hexString = str('{:x}'.format(capBitMask))
        while len(hexString) < 4: hexString = '0'+ hexString
        #log.debug("LLDP device type '%s' capabilities %s" % (self.devType,capabilities))
        return hexString + hexString
    
    ######################################################################
    def _packFaElement(self,faConfig: dict) -> str:
        if self.devType in DEFAULT.LLDP_DEVICE_TYPES:
            faDevType = DEFAULT.LLDP_DEVICE_TYPES[self.devType]['FA-Element']['ElementType']
            #log.debug("adapt FA device type '%s' => '%s'" % (self.devType,faDevType))
        else:
            log.warning("FA device type '%s' unknow, take 'OVS'" % self.devType)
            faDevType = DEFAULT.LLDP_DEVICE_TYPES['OVS']['FA-Element']['ElementType']
        
        count = 1
        for type in DEFAULT.FA_ELEMENT_TYPES:
            if faDevType == type:
                faElementType = str('{:x}'.format(count << 2))
                break
            count += 1
        
        if not faConfig['State'] == 'untagged':
            pos = DEFAULT.FA_ELEMENT_STATE_TAGGING.index(faConfig['State'])
            faElementType = str('{:x}'.format(count << 2 | pos << 1))
        else:
            pos = 0
        if faConfig['ProvMode'] == 'VLAN':
            faElementType = str('{:x}'.format(count << 2 | pos << 1 | 1))
        if len(faElementType) == 1:
            faElementType = '0'+faElementType
        if faConfig['ProvMode'] == 'SPB':
            mgmtVlan = int(faConfig['MgmtVlan']) | 32768            # 1000000000000000 => 0x8000 => 32768 
        else:
            mgmtVlan = int(faConfig['MgmtVlan'])
        
        if faConfig['State'] == 'untagged':
            mgmtVlan = mgmtVlan | 16384                                 # 0100000000000000 => 0x4000 => 16384
        payload  = faElementType+f'{mgmtVlan:0>4X}'
        payload += DEFAULT.FA_ELEMENT_RESERVED + self.systemId
        return DEFAULT.TLV_OUI_AVAYA+DEFAULT.TLV_FA_ELEMENT+self._hmacSha256(payload)+payload

    ######################################################################
    def _lldpHeader(self) -> None:
        nicNameLength= len(self.nic['name'])
        dst_addr     = bytes.fromhex(DEFAULT.LLDP_DST_MAC)
        src_addr     = bytes.fromhex(self.nic['MAC'])
        ethertype    = bytes.fromhex(DEFAULT.LLDP_PROTOCOL_ID)
        lldpChassis  = bytes.fromhex("020704"+self.nic['MAC'])
        lldpPort     = bytes.fromhex("04"+f'{nicNameLength+1:0>2X}'+"05"+ self.nic['name'].encode("utf-8").hex())
        lldpTtl      = bytes.fromhex("0602"+hex(DEFAULT.LLDP_TTL)[2:].zfill(4))
        lldpSysName  = bytes.fromhex("0a"+f'{len(self.sysName):0>2X}'+ self.sysName.encode("utf-8").hex())
        lldpSysDesc  = bytes.fromhex("0c"+f'{len(self.sysDesc):0>2X}'+ self.sysDesc.encode("utf-8").hex())
        lldpCapabili = bytes.fromhex("0e04"+self._packLldpCapabilities())
        lldpMgmtAddr = bytes.fromhex("100c0501"+inet_aton(self.nic['IP']).hex()+"010000000000")
        self.header  = b"".join([dst_addr,src_addr,ethertype,lldpChassis,lldpPort,lldpTtl,lldpSysName,lldpSysDesc,lldpCapabili,lldpMgmtAddr])

    ######################################################################
    def _hmacSha256(self,payload):
        if self.msgAuth:
            if type(payload) != bytes: payload = bytes.fromhex(payload)
            if self.hmacSha256:
                return ctypes.c_char_p(self.hmacSha256.get(self.secret,len(self.secret),payload,len(payload))).value.decode("utf-8")
            else:
                return hmac.new(self.secret,payload,hashlib.sha256).hexdigest()
        else:
            result = ''
            while len(result) < 64: result += '0'
            return result
    
    ######################################################################
    def updateFaAssignment(self, config: dict) -> None:
        lldpFaElementHex = self._packFaElement(config['LLDP']['FA-Element'])
        lenght = int( len(lldpFaElementHex)  / 2 )
        orgSpecific_lenght = hex(int(DEFAULT.TLV_TYPE_MASK,16) ^ int(f'{lenght:0>4X}',16))[2:]
        lldpFaElement= bytes.fromhex( orgSpecific_lenght + lldpFaElementHex )
        bindings = 0
        if config['VM']:
            assignment = ""
            for index in config['VM']:
                vlanId = int(index)
                isid   = int(config['VM'][index]['isid'])
                assignment += f'{vlanId:0>4X}'+ f'{isid:0>6X}'
                bindings += 1
            lldpFaAssignHex=DEFAULT.TLV_OUI_AVAYA+DEFAULT.TLV_FA_ASSINMENT+self._hmacSha256(assignment)+assignment
            lenght = int( len(lldpFaAssignHex) / 2 )
            orgSpecific_lenght = hex(int(DEFAULT.TLV_TYPE_MASK, 16) ^ int(f'{lenght:0>4X}',16))[2:]
            lldpFaAssign = bytes.fromhex( orgSpecific_lenght + lldpFaAssignHex )
        else:
            lldpFaAssign = b""
        lldpEndPdu = bytes.fromhex(DEFAULT.LLDP_PDU_END)
        self.lldpFrame = b"".join([self.header,lldpFaElement,lldpFaAssign,lldpEndPdu])

#####################################################################################################
