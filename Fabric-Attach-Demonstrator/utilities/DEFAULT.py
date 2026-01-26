###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 27. Nov. 2023
#

__version__ = "1.1.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

PLATFORM    = 'vFAD-NG'
VERSION     = __version__
ROOT_DIR    = "/root/vfad-ng/"
CONFIG_FILE = "/etc/vFAD_config.json"
LLDP_FILE   = "/etc/vFAD_LLDP_in.json"
LOG_FILE    = "/var/log/vFAD.log"
LOG_LEVEL   = 'INFO'                                    # DEBUG / INFO / WARNING
INIT_CONFIG = {
    "Platform": "vFAD-NG",
    "LOG_LEVEL": LOG_LEVEL,
    "LLDP": {
        "devType": "AP",
        "FA-Element": {
            "State": "tagged only",
            "ProvMode": "disabled",
            "MgmtVlan": 0,
            "msgAuth": True,
            "secret": "",
        }
    },
    "Version": __version__,
    "VM": dict()
}
MCAST_TTL   = 20
VM_STATS    = {
    'vlanId': 0,
    'isid': 0,
    'ip': 0,
    'dgw': 0,
    "iperf": False,
    "web": False,
    'ping': {},
    'mcast': {
        'server': 0,
        'client': 0
    }
}
LLDP_CONFIG = {
    'sysName': 'vFAD-NG',
    'sysDesc': 'Fabric Attach Demonstrator NG (%s)' % __version__
}
MAIN_CYCLE  = 0.1
VM_CYCLE    = 0.3
VM_DGW_CHECK= 10         # VM_CYCLE * VM_DGW_CHECK = 

#########  never touch this following parameter  #########
# https://www.rapidtables.com/convert/number/binary-to-hex.html
ETH_P_ALL               = 0x0003
VLAN_MASK               = 0x0FFF
## LLDP Protocol:
LLDP_UPDATE             = 5
LLDP_TTL                = 20                        # LLDP_UPDATE * 4
LLDP_DST_MAC            = "0180c200000e"
LLDP_PROTOCOL_ID        = "88cc"
LLDP_PDU_END            = "0000"
# LLDP Length:
LLDP_TLV_LEN            = 9
LLDP_TLV_HEADER_LEN     = 2
LLDP_TLV_OUI_LEN        = 3
LLDP_TLV_SUBTYPE_LEN    = 1
# LLDP Protocol Bit Mask:
TLV_TYPE_MASK           = "fe00"
LLDP_TLV_LEN_MASK       = 0x01ff
# LLDP TLV standard Type:
LLDP_PDUEND             = 0x00
LLDP_TLV_TYPE_PORTID    = 0x02
LLDP_TLV_TTL            = 0x03
LLDP_TLV_SYS_NAME       = 0x05
LLDP_TLV_SYS_DESCRIPTION= 0x06
LLDP_TLV_CAPABILITIES   = 0x07
LLDP_TLV_MGMT_ADDRESS   = 0x08
LLDP_TLV_ORG_SPECIFIC   = 0x7f
LLDP_CAPABILITY_MAP     = ['Other','Repeater','Bridge','WLAN-AP','Router','Telephone','DOCSIS CableDevice','Station only']
# LLDP FA TLV:
TLV_OUI_AVAYA             = "00040d"
TLV_FA_ELEMENT            = "0b"                # 11
TLV_FA_ASSINMENT          = "0c"                # 12
TLV_FA_ASSIN_BIND_LEN     = 5
FA_ELEMENT_STATE_TAGGING  = ['tagged only','tagged & untagged','untagged']
FA_ELEMENT_STATE_PROVISION= ['disabled','SPB','VLAN']
FA_ELEMENT_RESERVED       = "00"
FA_ELEMENT_TYPES          = ['Other','Server','Proxy','Server no authentication','Proxy no authentication','WLAN Type 1','WLAN Type 2','Switch','Router','Phone','Camera','Video','Security','Virtual Switch','xServer','ONA SDN mode','ONA SBPOIP mode','ISW RingV2']
FA_ASSIN_BIND_STATE       = ['unknow','pending','active','reject']
LLDP_DEVICE_TYPES         = {
    'Fabric Engine': {
        'LLDP': ['Bridge','Router'],
        'FA-Element': {
            'ElementType': 'Server',
            'State': 'tagged only',
            "ProvMode": "SPB",
            'MgmtVlan': 0
        }
    },
    'Switch Engine': {
        'LLDP': ['Bridge','Router'],
        'FA-Element': {
            'ElementType': 'Proxy',
            'State': 'tagged only',
            "ProvMode": "VLAN",
            'MgmtVlan': 0
        }
    },
    'ISW Switch': {
        'LLDP': ['Bridge','Router'],
        'FA-Element': {
            'ElementType': 'ISW RingV2',
            'State': 'tagged & untagged',
            "ProvMode": "disabled",
            'MgmtVlan': 0
        }
    },
    'OVS': {
        'LLDP': ['Bridge','Router'],
        'FA-Element': {
            'ElementType': 'Virtual Switch',
            'State': 'tagged only',
            "ProvMode": "disabled",
            'MgmtVlan': 0
        }
    },
    'AP': {
        'LLDP': ['WLAN-AP'],
        'FA-Element': {
            'ElementType': 'WLAN Type 1',
            'State': 'tagged & untagged',
            "ProvMode": "disabled",
            'MgmtVlan': 0
        }
    },
    'Phone': {
        'LLDP': ['Bridge','Telephone'],
        'FA-Element': {
            'ElementType': 'Phone',
            'State': 'tagged & untagged',
            "ProvMode": "disabled",
            'MgmtVlan': 0
        }
    },
    'Camera': {
        'LLDP': ['Station only'],
        'FA-Element': {
            'ElementType': 'Camera',
            'State': 'untagged',
            "ProvMode": "disabled",
            'MgmtVlan': 0
        }
    },
}
