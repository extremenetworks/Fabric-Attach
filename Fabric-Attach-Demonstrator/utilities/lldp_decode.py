###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 26. Oct. 2023
#            updated 19.05.2025

# https://www.rapidtables.com/convert/number/hex-to-decimal.html

__version__ = "1.0.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import logging, time, ctypes, os, os.path, subprocess, hashlib, hmac
from struct import unpack
from utilities import DEFAULT

#####################################################################################################
log = logging.getLogger('vFAD')

#####################################################################################################
class init():
    '''LLDP recieve interface'''

    ######################################################################
    def __init__(self, osInfo: dict, faSettings: dict) -> object:
        log.debug("%s (%s) is starting" % (init.__doc__,__version__))
        self.osInfo     = osInfo
        self.packet     = None
        self.data       = dict()
        self.error      = False
        self.msgAuth    = faSettings['msgAuth']
        self.secret     = faSettings['secret'].encode("UTF-8")
        
        self._loadHashLibrary()

   ######################################################################
    def __repr__(self) -> dict:
        return '%s' % self.__dict__
        
    ######################################################################
    def __del__(self) -> None:
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
    def _unpackLldpFrame(self, eth_payload: bytes):
        while eth_payload:
            tlv_header  = unpack('!H', eth_payload[:DEFAULT.LLDP_TLV_HEADER_LEN])
            tlv_type    = (tlv_header[0] & int(DEFAULT.TLV_TYPE_MASK, 16)) >> DEFAULT.LLDP_TLV_LEN
            tlv_data_len= (tlv_header[0] & DEFAULT.LLDP_TLV_LEN_MASK)
            tlv_payload = eth_payload[DEFAULT.LLDP_TLV_HEADER_LEN:DEFAULT.LLDP_TLV_HEADER_LEN + tlv_data_len]

            tlv_oui     = None
            tlv_subtype = None
            if tlv_type == DEFAULT.LLDP_TLV_ORG_SPECIFIC:
                _tlv_oui    = unpack('!%s' % ('B' * DEFAULT.LLDP_TLV_OUI_LEN),tlv_payload[:DEFAULT.LLDP_TLV_OUI_LEN])
                tlv_subtype = unpack('!B', tlv_payload[DEFAULT.LLDP_TLV_OUI_LEN:DEFAULT.LLDP_TLV_OUI_LEN+DEFAULT.LLDP_TLV_SUBTYPE_LEN])[0]
                tlv_payload = tlv_payload[DEFAULT.LLDP_TLV_OUI_LEN+DEFAULT.LLDP_TLV_SUBTYPE_LEN:]
                
                # Covert oui from list to hex/decimals
                tlv_oui = str()
                for bit in _tlv_oui:
                    tlv_oui += hex(bit).strip('0x').rjust(2, '0')
                tlv_oui = int(tlv_oui, 16)

            elif tlv_type == DEFAULT.LLDP_PDUEND:
                break                                   # reach the end

            eth_payload = eth_payload[DEFAULT.LLDP_TLV_HEADER_LEN + tlv_data_len:]
            yield (tlv_type,tlv_oui,tlv_subtype,tlv_payload)

    ######################################################################
    def _unpackLldpCapabilities(self, inData: bytes) -> list:
        try:
            capBitMask     = bin(unpack('!H', inData[2:])[0])[2:].zfill(8)
            capEnadBitMask = bin(unpack('!H', inData[:2])[0])[2:].zfill(8)
            cap    = [elem for bit, elem in zip(capBitMask,    reversed(DEFAULT.LLDP_CAPABILITY_MAP)) if bit == '1']
            capEna = [elem for bit, elem in zip(capEnadBitMask,reversed(DEFAULT.LLDP_CAPABILITY_MAP)) if bit == '1']
        except:
            cap    = ['unknow']
            capEna = ['unknow']
        return ' '.join(cap) +"/"+ ' '.join(capEna)
    
    ######################################################################
    def _unpackLldpTlvFaElement(self, tlv_payload: bytes) -> dict:
        data    = dict()
        pointer = 32
        if self.msgAuth:
            if self.hmacSha256:
                if tlv_payload[:pointer].hex() == ctypes.c_char_p(self.hmacSha256.get(self.secret,len(self.secret),tlv_payload[pointer:],len(tlv_payload[pointer:]))).value.decode("utf-8"):
                    data['msgAuth'] = 'success'
                else:
                    data['msgAuth'] = 'failed'
            else:
                if tlv_payload[:pointer].hex() == hmac.new(self.secret,tlv_payload[pointer:],hashlib.sha256).hexdigest():
                    data['msgAuth'] = 'success'
                else:
                    data['msgAuth'] = 'failed'
        else:
            data['msgAuth'] = 'disabled'
        
        header = unpack('!H', tlv_payload[pointer:pointer+2])
        typeNum = ((header[0] & 0xfc00) >> 10) - 1
        if typeNum < len(DEFAULT.FA_ELEMENT_TYPES):
            data['Type']  = DEFAULT.FA_ELEMENT_TYPES[typeNum]
        else:
            data['Type']  = 'unknow %s' % typeNum
        data['State']     = DEFAULT.FA_ELEMENT_STATE_TAGGING[(  header[0] & 0x0200) >> 9]
        data['ProvMode']  = DEFAULT.FA_ELEMENT_STATE_PROVISION[(header[0] & 0x0180) >> 7]
        mgmtVlan          = unpack('!H', tlv_payload[pointer+1:pointer+3])
        data['MgmtVlan']  = (mgmtVlan[0] & DEFAULT.VLAN_MASK)
        if mgmtVlan[0] & 0x4000:
            data['State'] = DEFAULT.FA_ELEMENT_STATE_TAGGING[2]
        data['System-ID'] = ':'.join('%02x' % byte for byte in tlv_payload[pointer+4:])
        return data
    
    ######################################################################
    def _unpackLldpTlvFaAssignment(self, tlv_payload: bytes) ->list:
        pointer = 32
        bindings = list()
        while pointer < len(tlv_payload):
            binding = dict()
            stateVlan = unpack('!H', tlv_payload[pointer:pointer+2])
            stateNumber = (stateVlan[0] & 0xF000) >> 12
            if stateNumber >= 0 and stateNumber <= 3:
                binding['state'] = DEFAULT.FA_ASSIN_BIND_STATE[ stateNumber ]
            else:
                binding['state'] = 'reject'
            binding['vlanId'] = (stateVlan[0] & DEFAULT.VLAN_MASK)
            isid = unpack('!HH', tlv_payload[pointer+1:pointer+5])
            binding['isid'] = (isid[0] & 0x00FF) * 65536 + isid[1]
            pointer += DEFAULT.TLV_FA_ASSIN_BIND_LEN
            bindings.append(binding)
        return bindings
    
    ######################################################################
    def decode(self, packet: bytes, store: bool = True) -> bool:
        if store and packet == self.packet:
            if 'ttl' in self.data:
                self.data['expire'] = time.time() + self.data['ttl']
            else:
                self.data['expire'] = time.time()
            #log.debug("LLDP inbound cache match")
            return False
        else:
            #log.debug("LLDP inbound cache no match")
            data = {
                'name': '','capabilities': '','description': '','port': '',
                'FA-Element': {}
            }
            for tlv_parse_rv in self._unpackLldpFrame( packet ):
                tlv_type, tlv_oui, tlv_subtype, tlv_payload = tlv_parse_rv
                if tlv_type == DEFAULT.LLDP_TLV_TYPE_PORTID:
                    try:                                           
                        data['port'] = tlv_payload[1:].decode("utf-8")      # Interface Name
                    except:
                        try:
                            data['port'] = unpack("!HHH",tlv_payload)       # MAC address
                        except:
                            data['port'] = ''
                elif tlv_type == DEFAULT.LLDP_TLV_TTL:
                    data['ttl'] = int("".join(map(str, unpack("!H",tlv_payload))))
                    data['expire'] = time.time() + data['ttl']
                elif tlv_type == DEFAULT.LLDP_TLV_SYS_NAME:
                    data['name'] = tlv_payload.decode("utf-8")
                elif tlv_type == DEFAULT.LLDP_TLV_SYS_DESCRIPTION:
                    data['description'] = tlv_payload.decode("utf-8")
                elif tlv_type == DEFAULT.LLDP_TLV_CAPABILITIES:
                    data['capabilities'] = self._unpackLldpCapabilities(tlv_payload)
                elif tlv_type == DEFAULT.LLDP_TLV_MGMT_ADDRESS:
                    data['ip'] = ".".join(map(str, unpack("!BBBB",tlv_payload[2:6])))
                elif tlv_type == DEFAULT.LLDP_TLV_ORG_SPECIFIC and tlv_oui == int(DEFAULT.TLV_OUI_AVAYA, 16):
                    if tlv_subtype == int(DEFAULT.TLV_FA_ELEMENT, 16):
                        data['FA-Element'] = self._unpackLldpTlvFaElement(tlv_payload)
                    elif tlv_subtype == int(DEFAULT.TLV_FA_ASSINMENT, 16):
                        data['FA-Assinment'] = self._unpackLldpTlvFaAssignment(tlv_payload)
        
        if store:
            self.data   = data
            self.packet = packet
            self.change = True
            return True
        else:
            return data
    
    ######################################################################
    def errorMsg(self) -> None:
        msg = self.error
        self.error = False
        return msg

    ######################################################################
    def clearData(self) -> None:
        self.packet = None
        self.data = {'FA-Element': False}

#####################################################################################################
