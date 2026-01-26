###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 26. Oct. 2023
#            updated 19.05.2025

__version__ = "1.0.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import os,logging,re,subprocess,json
from utilities import DEFAULT

#####################################################################################################
PATTERN_IP    = re.compile(r"\s((\d{1,3}\.){3}\d{1,3})\/(\d+)\s")
PATTERN_ROUTE = re.compile(r"((\d{1,3}\.){3}\d{1,3}\/\d+|default)\s+via\s+((\d{1,3}\.){3}\d{1,3})\s")

log     = logging.getLogger('vFAD')
nicData = {'loaded': False, 'name': 'lo', 'MAC': '00:00:00:00:00:00', 'IP': '127.0.0.1'}

#####################################################################
def getNicData() -> str:
    if not nicData['loaded']:
        result = json.loads(os.popen('ip --json address').read())
        log.debug("NIC lookup data result:\n%s" % json.dumps(result,indent=2,sort_keys=True))
        for ifFace in result:
            if ifFace['link_type'] == 'ether' and ifFace['ifname'].startswith('e'):
                if ifFace['addr_info']:
                    for ip in  ifFace['addr_info']:
                        if ip['family'] == 'inet':
                            nicData['IP'] = ip['local']
                else:
                    globals()['nicData']['name'] = ifFace['ifname']
                    globals()['nicData']['MAC'] = ifFace['address']
        if nicData['name'] == 'lo' or nicData['name'] == 'IP' == '127.0.0.1':
            log.warning("lookup NIC data failed: %s" % json.dumps(nicData, sort_keys=True))
        else:
            log.debug("lookup NIC data: %s" % json.dumps(nicData, sort_keys=True))
        globals()['nicData']['loaded'] = True
    return nicData
    
#####################################################################
def generateMacAddress(id: int) -> str:
    prefix = '02'
    mid = f'{int(id):x}'
    while len(mid) < 4: mid = '0'+ mid
    nic = getNicData()
    physicalMac = nic['MAC'].replace(':','')
    virtualMac = ':'.join(map(''.join,zip(*[iter(prefix+mid+physicalMac[6:])]*2)))
    log.debug("VM-%s FA NIC %s virtual MAC '%s'" % (id,nic['name'],virtualMac))
    return virtualMac

#####################################################################
def execute(cmds: str,hide: bool = False) -> str:
    if not hide:
        #log.debug(" BASH  STDIN: '%s'" % cmds.replace("\n","\n    "))
        pass
    if ' &' in cmds:
        os.system(cmds)
    else:
        process = subprocess.Popen('/bin/bash',stdin=subprocess.PIPE,stdout=subprocess.PIPE,cwd=DEFAULT.ROOT_DIR,text=True)
        stdout, stderr = process.communicate(cmds)
        if stdout and not hide:
            #log.debug(" BASH STDOUT:\n\t%s" % stdout.replace("\n","\n    "))
            pass
        if stderr:
            log.warning("BASH STDERR: '%s'" % stderr)
        return stdout

#####################################################################################################
def bringUpNic(nicName: str) -> None:
    cmds = '''
sysctl -w net.ipv6.conf.all.disable_ipv6=1
ip link set dev <NIC> up
'''
    execute(cmds.replace('<NIC>',nicName))

#####################################################################################################
def commition(nic: dict,vmId: int,config: dict) -> None:
    cmds = '''
ip link add name VLAN-<ID> link <NIC> type vlan id <ID>
ip link set dev VLAN-<ID> up
ip netns add VM-<ID>
ip link set VLAN-<ID> netns VM-<ID>
ip netns exec VM-<ID> ip link set dev VLAN-<ID> address <MAC>
ip netns exec VM-<ID> sysctl -w net.ipv6.conf.all.disable_ipv6=1
sleep 0.1
ip netns exec VM-<ID> ip link set dev VLAN-<ID> up'''
    if config['mcast']['server']:
        cmds += '\nip netns exec VM-<ID> ip route add 224.0.0.0/4 dev VLAN-<ID>'
    if not config['dhcp']:
        cmds += '\nip netns exec VM-<ID> ip address add %s dev VLAN-<ID>' % config['ip']
        if config['dgw']:
            cmds += '\nip netns exec VM-<ID> ip route add 0.0.0.0/0 via %s' % config['dgw']
    nic =  getNicData()
    cmds = cmds.replace('<NIC>',nic['name'])
    cmds = cmds.replace('<ID>',str(vmId))
    cmds = cmds.replace('<MAC>',generateMacAddress(vmId))
    execute(cmds)

#####################################################################################################
def checkDgw(vmId: int,config: dict) -> None:
    if not config['dhcp'] and config['dgw']:
        if not execute('ip netns exec VM-%s ip route | grep default' % vmId):
            execute('ip netns exec VM-%s ip route add 0.0.0.0/0 via %s\n' % (vmId,config['dgw']))
            log.debug("VM-%s setup DGW again" % vmId)

#####################################################################################################
def decommition(vlanId: int) -> None:
    cmds = '''
ip netns exec VM-<ID> ip link set dev VLAN-<ID> down
ip netns exec VM-<ID> ip link set VLAN-<ID> netns 1
ip netns delete VM-<ID>
ip link delete name VLAN-<ID>'''.replace('<ID>',str(vlanId))
    execute(cmds)

#####################################################################################################
def dhcpAquire(vlanId: int) -> None:
    cmds = 'ip netns exec VM-<ID> dhclient -4 -q VLAN-<ID> > /dev/null 2>&1 &'
    execute(cmds.replace('<ID>',str(vlanId)),True)

#####################################################################################################
def dhcpRenew(vlanId: int) -> None:
    cmds = "kill $(ip netns pids VM-<ID> | xargs ps -o pid,command -p > /dev/null 2>&1 | grep dhclient | awk '{print $1}')  > /dev/null 2>&1"
    execute(cmds.replace('<ID>',str(vlanId)),True)
    cmds = "ip netns exec VM-<ID> dhclient -4 -q VLAN-<ID> 2>1 > /dev/null &"
    execute(cmds.replace('<ID>',str(vlanId)),True)

#####################################################################################################
def dhcpRelease(vlanId: int) -> None:
    cmd = 'ip netns exec VM-<ID> dhclient -r -q VLAN-<ID> 2>1 > /dev/null'
    execute(cmd.replace('<ID>',str(vlanId)),True)

#####################################################################################################
def dhcpKill(vlanId: int) -> None:
    cmd = "kill $(ip netns pids VM-<ID> | xargs ps -o pid,command -p > /dev/null 2>&1 | grep dhclient | awk '{print $1}') > /dev/null 2>&1"
    execute(cmd.replace('<ID>',str(vlanId)),True)

#####################################################################################################
def iperfSetup(vlanId: int) -> None:
    cmd = 'ip netns exec VM-<ID> iperf3 -4 --server --port 5201 --daemon'
    execute(cmd.replace('<ID>',str(vlanId)))

#####################################################################################################
def iperfKill(vlanId: int) -> None:
    cmd = "kill $(ip netns pids VM-<ID> | xargs ps -o pid,command -p 2> /dev/null | grep iperf3 | awk '{print $1}')  > /dev/null 2>&1"
    execute(cmd.replace('<ID>',str(vlanId)))

#####################################################################################################
def webSetup(vlanId: int) -> None:
    cmd = 'ip netns exec VM-<ID> /usr/bin/python3 utilities/VM_WEB_server.py &'
    execute(cmd.replace('<ID>',str(vlanId)))

#####################################################################################################
def webKill(vlanId: int) -> None:
    cmd = "kill $(ip netns pids VM-<ID> | xargs ps -o pid,command -p 2> /dev/null | grep VM_WEB_server.py | awk '{print $1}')  > /dev/null 2>&1"
    execute(cmd.replace('<ID>',str(vlanId)))

#####################################################################
def status(vlanId: int) -> dict:
    state = {'ip': None, 'dgw': None, 'route': dict()}
    result = execute("ip netns exec VM-%s ip -o -4 address show dev VLAN-%s" % (vlanId,vlanId), True)
    match = PATTERN_IP.search( result )
    if match:
        state['ip'] = match.group(1) +'/'+ match.group(3)
    else:
        state['ip'] = None
        return state

    result = execute("ip netns exec VM-%s ip -o -4 route show dev VLAN-%s  | grep via" %(vlanId,vlanId), True)
    for line in result.splitlines():
        match = PATTERN_ROUTE.search( line )
        if match:
            if match.group(1) == 'default':
                state['dgw']  = match.group(3)
            else:
                state['route'] = { match.group(1): match.group(3) }
    return state

#####################################################################################################
