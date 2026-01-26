#!/usr/bin/env python3

###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 26. Oct. 2023
#

__version__ = "1.1.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

# apt install python3-flask python3-flask-socketio python3-eventlet
# apt install python3-jsonschema

import json,subprocess,time,atexit,signal,re,copy,threading,os
import jsonschema.exceptions
from flask import Flask,render_template,request,send_from_directory,send_file
from flask_socketio import SocketIO,Namespace
from multiprocessing import Process,Event,Queue
from utilities import DEFAULT,VM_dealer,common,lldpd,VM_NIC_control
from utilities.validator import configValidator

######################################################################
REGEX_IP_MASK = re.compile(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\/([1-9]|1[0-9]|2[0-9]|30)$")
REGEX_IP      = re.compile(r"^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$")
REGEX_MCAST   = re.compile(r"^2(?:2[4-9]|3\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]\d?|0)){3}:(\d{1,4}|[1-5]\d{4}|6[0-4]\d{3}|654\d{2}|655[0-3]\d)$")

######################################################################
log         = common.setupLogger()
config      = dict()
app         = Flask(__name__,static_folder='static')                # WEB server
socketio    = SocketIO(app,async_mode="eventlet",                   # WEBsocket server
                        cors_allowed_origins="*")                   # allow CORS (DEVELOPMENT ONLY!)
event       = Event()                                               # for multiprocessing
lldpDaemon  = None                                                  # for multiprocessing
lldpQueue   = {'cfg': Queue(), 'in':  Queue(), 'out': Queue()}      # for multiprocessing
lldpState   = {'in':  dict(), 'out': dict()}                        # for multiprocessing
vmDealer    = None                                                  # for multiprocessing
vmQueue     = {'cfg': Queue(), 'state': Queue(), 'in': Queue()}     # for multiprocessing
vmState     = dict()
lock        = threading.Lock()                                      # semaphore
pendingCfg  = {'vm': False, 'lldp': False, 'web': False}
nic         = dict()

######################################################################
#                     LLDP Child Process                             #
######################################################################
def sigHandler(signum, frame) -> None:
    log.debug("main recive signal %s [%s]", signal.Signals( signum ).name, signum)
    event.set()
    time.sleep(DEFAULT.MAIN_CYCLE + 0.1)
    socketio.stop()
    exit(0)

######################################################################
def childSigHandler(signum, frame) -> None:
    log.debug("child recive signal %s [%s]", signal.Signals( signum ).name, signum)
    event.set()

######################################################################
def lldpChild(event,lldpQueue) -> None:
    signal.signal(signal.SIGABRT,childSigHandler)
    signal.signal(signal.SIGINT, childSigHandler)
    signal.signal(signal.SIGTERM,childSigHandler)
    signal.signal(signal.SIGQUIT,childSigHandler)
    #signal.signal(signal.SIGCHLD,childSigHandler)

    lldp  = lldpd.init(nic,config)
    state = {'in': False, 'out': False}
    stateCache = False
    while not event.is_set():
        start = time.time()
        if not lldpQueue['cfg'].empty():
            newConfig = lldpQueue['cfg'].get_nowait()
            lldp.loadConfig(newConfig)

        lldp.run()

        for direction in ['in','out']:
            if lldp.newData(direction):
                state[direction] = lldp.getData(direction)
                #log.debug("LLDP %s new data:\n%s" % (direction,json.dumps(state[direction],sort_keys=True,indent=2)))

        if state['in']:
            stateCache = copy.deepcopy(state['in'])

        for direction in ['in','out']:
            if state[direction] and lldpQueue[direction].empty():
                #log.debug("LLDP %s push in queue" % direction)
                lldpQueue[direction].put_nowait(state[direction])
                state[direction] = False

        wait = DEFAULT.MAIN_CYCLE - (time.time()-start)
        if wait > 0: time.sleep(wait)

    if stateCache:
        if 'expire' in stateCache:
            if stateCache['expire'] > time.time():
                common.writeFile(DEFAULT.LLDP_FILE,stateCache)
                log.debug("WEB write LLDP cached state data to file %s" % DEFAULT.LLDP_FILE)

    log.debug("leave LLDP child loop")

######################################################################
def vmChild(event,vmQueue):
    signal.signal(signal.SIGABRT,childSigHandler)
    signal.signal(signal.SIGINT, childSigHandler)
    signal.signal(signal.SIGTERM,childSigHandler)
    signal.signal(signal.SIGQUIT,childSigHandler)
    #signal.signal(signal.SIGCHLD,childSigHandler)

    vmDealer = VM_dealer.init(nic,config['VM'])

    state   = False
    vmConfig= False
    while not event.is_set():
        start = time.time()
        if not vmQueue['cfg'].empty():
            newConfig = vmQueue['cfg'].get_nowait()
            vmDealer.loadConfig(newConfig)

        if event.is_set(): break
        vmDealer.run()

        if event.is_set(): break
        if vmDealer.newConfig:
            vmConfig = vmDealer.getConfig()
        
        if event.is_set(): break
        if vmConfig and vmQueue['in'].empty():
            vmQueue['in'].put_nowait(vmConfig)
            vmConfig = False

        if event.is_set(): break
        if vmDealer.newStats:
            state = vmDealer.getStatus()
        
        if event.is_set(): break
        if state and vmQueue['state'].empty():
            vmQueue['state'].put_nowait(state)
            state = False

        if event.is_set(): break
        wait = DEFAULT.MAIN_CYCLE - (time.time()-start)
        if wait > 0: time.sleep(wait)
        
    vmDealer.exitHandler()
    log.debug("leave VM child loop")

######################################################################
#                         WEB-Server                                 #
######################################################################
@app.route('/')
def index() -> None:
    return render_template('index.html', async_mode=socketio.async_mode)

######################################################################
@app.route('/disclaimer')
def disclaimer() -> None:
    return render_template('disclaimer.html')

@app.route('/license')
def license() -> None:
    return render_template('license.html')

@app.route('/user-guide')
def user_guide() -> None:
    return send_file('templates/vFAD-NG_UserGuide.pdf')

#####################################################################
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path,'static'),'favicon.ico',mimetype='image/vnd.microsoft.icon')

#####################################################################
@app.route('/backup')
def backup ():
    if os.path.isfile(DEFAULT.CONFIG_FILE):
        log.info("provide backup config file %s" % DEFAULT.CONFIG_FILE)
        return send_file(DEFAULT.CONFIG_FILE,as_attachment=True)
    else:
        log.warning("provide backup config file %s failed, dosn't exists" % DEFAULT.CONFIG_FILE)
        return app.response_class(status=400)
    
#####################################################################
@app.route('/restore',methods=['POST'])
def restore ():
    log.info("got config restore request")
    fileHandler = request.files['file']
    if fileHandler:
        fileHandler.save('/tmp/vFAD_config.json')
        result,newConfig = common.loadConfig('/tmp/vFAD_config.json')
        if result:
            log.info("config restore accepted")
            common.writeConfig(newConfig)
            log.debug("restart vFAD")
            subprocess.Popen("/usr/bin/sleep 0.5; /usr/bin/systemctl restart vFAD.service",stdin=None,stdout=None,cwd='/',shell=True,text=True)
            event.set()
            return app.response_class(status=200)
        else:
           log.warning("config restore rejected, integrity is not given") 
           return app.response_class(status=400)
    else:
        log.warning("no restore config given, ignore restore request")
    return app.response_class(status=400)

#####################################################################
@app.route('/control',methods=['POST'])
def control() -> None:
    inbound  = request.get_json(silent=True)
    debugDisplay('inbound',request,inbound)

    outbound = dict()
    if 'action' in inbound:
        if inbound['action'] == 'reboot':
            outboundReturnCode = 201
            log.info("##################### REBOOT #####################")
            subprocess.Popen("/usr/bin/sleep 1; /usr/bin/systemctl reboot",stdin=None,stdout=None,cwd='/',shell=True,text=True)
            outbound['message'] = 'reboot in progress'
        elif inbound['action'] == 'shutdown':
            outboundReturnCode = 201
            log.info("##################### SHUTDOWN #####################")
            subprocess.Popen("/usr/bin/sleep 1; /usr/bin/systemctl poweroff", stdin=None,stdout=None,cwd='/',shell=True,text=True)
            outbound['message'] = 'shutdown in progress'
        elif inbound['action'] == 'reset':
            outboundReturnCode = 201
            log.info("##################### RESET #####################")
            outbound['message'] = 'reset in progress'
            for vmId in config['VM']:
                log.debug("trash 'VM-%s'" % vmId)
                with lock:
                    del vmState[vmId]
                    pendingCfg['lldp'] = True
                    pendingCfg['vm']   = True
            globals()['config'] = copy.deepcopy(DEFAULT.INIT_CONFIG)
            common.writeConfig(config)
            event.set()
            subprocess.Popen("/usr/bin/sleep 0.5; /usr/bin/systemctl restart vFAD.service",stdin=None,stdout=None,cwd='/',shell=True,text=True)
        else:
            outboundReturnCode = 400
            outbound['message'] = 'Bad Request, unknow action'
            log.warning("unknow action '%s'" % inbound['action'])
    else:
        outboundReturnCode  = 400
        outbound['message'] = 'Bad Request'
        log.warning("control: no action ")

    debugDisplay('outbound',outbound,outboundReturnCode)
    return app.response_class(
        response = json.dumps(outbound),
        status   = outboundReturnCode,
        mimetype = 'application/json'
    )

#####################################################################
@app.route('/config',methods=['POST','PATCH','DELETE'])
def config() -> None:
    message = request.json

    log.debug("WEB-Client %s %s request:\n%s" % (
        request.environ.get('HTTP_X_REAL_IP',request.remote_addr),
        request.method,
        json.dumps(message,indent=2,sort_keys=True)
    ))

    if 'FA-Element' in message and request.method == 'PATCH':       # LLDP
        result = lldpConfigValidator(message)
        if not result:
            with lock:
                socketio.emit('outbound',{'data': json.dumps(config['LLDP'])},namespace='/')
            outboundReturnCode = 200
            outbound = {}
        else:
            outboundReturnCode = 400
            outbound = {'msg': result}

    elif 'vlanId' in message:                                       # VM
        actionMapping = {'POST': 'add','PATCH': 'update','DELETE': 'delete'}
        message['action'] = actionMapping[request.method]
        if 'action' in message:
            result = vmConfigValidator(message)
            if not result:
                with lock:
                    log.debug("push new config to all WEB clients:\n%s" % json.dumps(config['VM'],indent=2,sort_keys=True))
                    socketio.emit('config',{'data': json.dumps(config['VM'])},namespace='/')
                    log.debug("push new state to all WEB clients:\n%s" % json.dumps(vmState,indent=2,sort_keys=True))
                    socketio.emit('state', {'data': json.dumps(vmState)},namespace='/')
                outboundReturnCode = 200
                outbound = {}
            else:
                outboundReturnCode = 400
                outbound = {'msg': result}
    else:
        outboundReturnCode = 500
        outbound = {'msg': 'unknow request'}

    log.debug("WEB-Client %s %s response: %s %s" % (
        request.environ.get('HTTP_X_REAL_IP',request.remote_addr),
        request.method,
        outboundReturnCode,
        outbound
    ))
    return app.response_class(
        response = json.dumps(outbound),
        status   = outboundReturnCode,
        mimetype = 'application/json'
    )

######################################################################
#                      WebSocket-Server                              #
######################################################################
class webSocketServer(Namespace):
    ##################################################################
    def on_connect(self) -> None:
        ip = request.environ.get('HTTP_X_REAL_IP',request.remote_addr)
        # log.debug('WEB-Client %s connected' % ip)

        if lldpState['in']:
            with lock:
                socketio.emit('inbound',{'data': json.dumps(lldpState['in'])},namespace='/')
        if lldpState['out']:
            with lock:
                socketio.emit('outbound',{'data': json.dumps(lldpState['out'])},namespace='/')

        with lock:
            socketio.emit('config',{'data': json.dumps(config['VM'])},namespace='/')
            socketio.emit('state',{'data':  json.dumps(vmState)},namespace='/')
        socketio.emit('response', {'data': 'Connected', 'count': 0})

    ##################################################################
    def on_disconnect(self) -> None:
        ip = request.environ.get('HTTP_X_REAL_IP',request.remote_addr)
        # log.debug('WEB-Client %s disconnected' % ip)

######################################################################
def lldpConfigValidator(inConfig):
    globals()['config']['LLDP']['name']                     = inConfig['name']
    globals()['config']['LLDP']['description']              = inConfig['description']
    globals()['config']['LLDP']['devType']                  = inConfig['FA-Element']['Type']
    globals()['config']['LLDP']['FA-Element']['State']      = inConfig['FA-Element']['State']
    globals()['config']['LLDP']['FA-Element']['ProvMode']   = inConfig['FA-Element']['ProvMode']
    
    
    mgmtVlan = int(inConfig['FA-Element']['MgmtVlan'])
    if mgmtVlan >= 0 and mgmtVlan <= 4095:
        globals()['config']['LLDP']['FA-Element']['MgmtVlan'] = inConfig['FA-Element']['MgmtVlan']
    else:
        log.info("LLDP config droped, Mgmt VLAN is out of range 0-4095")
        return "Mgmt VLAN is out of range 0-4095"

    if 'msgAuth' in inConfig['FA-Element']:
        globals()['config']['LLDP']['FA-Element']['msgAuth'] = True
        globals()['config']['LLDP']['FA-Element']['secret']  = inConfig['FA-Element']['msgAuth']
    else:
        globals()['config']['LLDP']['FA-Element']['msgAuth'] = False
        globals()['config']['LLDP']['FA-Element']['secret']  = ''
    
    common.writeConfig(config)
    with lock:
        pendingCfg['lldp'] = True
    
    log.debug("LLDP config accepted")
    return False

######################################################################
def vmConfigValidator(inConfig):
    # check if the given config complies with the json schema
    # - performs type casts from str -> int, str -> bool
    # - adds default values if the key is not present

    vmId = str(inConfig['vlanId'])

    if inConfig['action'] == 'delete':
        if vmId in config['VM']:
            del inConfig['action']
            with lock:
                del globals()['config']['VM'][vmId]
                del globals()['vmState'][vmId]
                pendingCfg['lldp'] = True
                pendingCfg['vm']   = True
            common.writeConfig(config)
            return False
        else:
            log.warning("delete 'VM-%s' config failed, VM doesn't exists" % vmId)
            return "VM-%s doesn't exists" % vmId

    try:
        configValidator.validate(inConfig)
    except jsonschema.exceptions.ValidationError as error:
        return "Schema Error: %s" % str(error)
    
    if inConfig['action'] == 'add':
        if not vmId in config['VM']:
            del inConfig['action']
            with lock:
                globals()['config']['VM'][vmId] = copy.deepcopy(inConfig)
                globals()['vmState'][vmId] = DEFAULT.VM_STATS.copy()
                globals()['vmState'][vmId]['isid']   = globals()['config']['VM'][vmId]['isid']
                globals()['vmState'][vmId]['vlanId'] = globals()['config']['VM'][vmId]['vlanId']
                result = checkIntegrity('add',vmId)
                if result:
                    del globals()['vmState'][vmId]
                    return result
                pendingCfg['lldp'] = True
                pendingCfg['vm']   = True
            common.writeConfig(config)
            log.debug("add 'VM-%s' config accepted" % vmId)
            return False
        else:
            log.warning("add 'VM-%s' config failed, VM exists alreday" % vmId)
            return "VM-%s exists alreday" % vmId

    if inConfig['action'] == 'update':
        if vmId in config['VM']:
            del inConfig['action']
            if json.dumps(config['VM'][vmId], sort_keys=True) == json.dumps(inConfig,sort_keys=True):
                log.info("update 'VM-%s' config droped, is the same than existing one" % vmId)
                return "config is the same than existing one"
            else:
                with lock:
                    globals()['config']['VM'][vmId] = copy.deepcopy(inConfig)
                    vmStateBackup = vmState[vmId].copy()
                    globals()['vmState'][vmId] = DEFAULT.VM_STATS.copy()
                    result = checkIntegrity('update',vmId)
                    if result:
                        globals()['vmState'][vmId] = vmStateBackup
                        return result
                    pendingCfg['lldp'] = True
                    pendingCfg['vm']   = True
                common.writeConfig(config)
                log.debug("update 'VM-%s' config accepted" % vmId)
                return False
        else:
            log.warning("update 'VM-%s' config failed, VM not exists" % vmId)
            return "VM-%s not exists" % vmId

######################################################################
def checkIntegrity(context: str,vmId: str) -> bool:
    if config['VM'][vmId]['dhcp']:
        globals()['config']['VM'][vmId]['ip']  = ''
        globals()['config']['VM'][vmId]['dgw'] = ''
    else:
        if config['VM'][vmId]['ip']:
            match = REGEX_IP_MASK.search(config['VM'][vmId]['ip'])
            if not match:
                msg = "IP with subnet mask '%s' is not a valide" % config['VM'][vmId]['ip']
                del globals()['config']['VM'][vmId]
                log.warning("%s 'VM-%s' config wrong, %s" % (context,vmId,msg))
                return msg
            if config['VM'][vmId]['dgw']:
                match = REGEX_IP.search(config['VM'][vmId]['dgw'])
                if not match:
                    msg = "Gateway '%s' is not a valide IP address" % config['VM'][vmId]['dgw']
                    del globals()['config']['VM'][vmId]
                    log.warning("%s 'VM-%s' config wrong, %s" % (context,vmId,msg))
                    return msg
    
    for ip in config['VM'][vmId]['ping']:
        if ip == '': continue
        match = REGEX_IP.search(ip)
        if match:
            if ip == config['VM'][vmId]['ip'].split('/')[0]:
                msg = "ping IP '%s' canot be the same like VM IP address" % ip
                del globals()['config']['VM'][vmId]
                log.warning("%s 'VM-%s' config wrong, %s" % (context,vmId,msg))
                return msg
            if ip == config['VM'][vmId]['dgw']:
                msg = "ping IP '%s' canot be the same like Default Gateway IP address" % ip
                del globals()['config']['VM'][vmId]
                log.warning("%s 'VM-%s' config wrong, %s" % (context,vmId,msg))
                return msg
            globals()['vmState'][vmId]['ping'][ip] = 0
        else:
            msg = "ping IP '%s' is not a valide IP address" % ip
            del globals()['config']['VM'][vmId]
            log.warning("%s 'VM-%s' config wrong, %s" % (context,vmId,msg))
            return msg
    
    if not config['VM'][vmId]['mcast']['client'] == '':
        match = REGEX_MCAST.search(config['VM'][vmId]['mcast']['client'])
        if not match:
            msg = "Mcast-Client '%s' is not a valide multicast IP address with UDP port" % config['VM'][vmId]['mcast']['client']
            del globals()['config']['VM'][vmId]
            log.warning("%s 'VM-%s' config wrong, %s" % (context,vmId,msg))
            return msg
    if not config['VM'][vmId]['mcast']['server'] == '':
        match = REGEX_MCAST.search(config['VM'][vmId]['mcast']['server'])
        if not match:
            msg = "Mcast-Server '%s' is not a valide multicast IP address with UDP port" % config['VM'][vmId]['mcast']['server']
            del globals()['config']['VM'][vmId]
            log.warning("%s 'VM-%s' config wrong, %s" % (context,vmId,msg))
            return msg
        else:
            log.debug("%s 'VM-%s' config, Mcast-Server '%s' is a valide multicast IP address" % (context,vmId,config['VM'][vmId]['mcast']['server']))

    return False

######################################################################
def webSocketBackgroundThread() -> None:
    log.debug('WEB-Server background thread started')
    
    while not event.is_set():
        start  = time.time()

        if pendingCfg['lldp'] and lldpQueue['cfg'].empty():
            with lock:
                globals()['lldpQueue']['cfg'].put_nowait(config)
                globals()['pendingCfg']['lldp'] = False
        
        if event.is_set(): break
        if pendingCfg['vm'] and vmQueue['cfg'].empty():
             with lock:
                globals()['vmQueue']['cfg'].put_nowait(config['VM'])
                globals()['pendingCfg']['vm'] = False

        if event.is_set(): break
        for direction in ['in','out']:
            if not lldpQueue[direction].empty():
                with lock:
                    if 'noData' in lldpState['in']:
                        globals()['lldpState']['in'] = dict()
                    lldpState[direction] = lldpQueue[direction].get_nowait()
                    log.debug("push LLDP %s status to all WEB clients:\n%s" % (direction,json.dumps(lldpState[direction],indent=2,sort_keys=True)))
                    socketio.emit(direction+'bound',{'data': json.dumps(lldpState[direction])},namespace='/')
        
        if event.is_set(): break
        if 'FA-Assinment' in lldpState['in']:
            update = False
            for assign in lldpState['in']['FA-Assinment']:
                vmId = str(assign['vlanId'])
                if not vmId in vmState:
                    continue
                if assign['state'] == 'active':
                    if vmState[vmId]['vlanId'] != 1:
                        with lock:
                            globals()['vmState'][vmId]['vlanId'] = 1
                            globals()['vmState'][vmId]['isid']   = 1
                        update = True
                elif assign['state'] == 'reject':
                    if vmState[vmId]['vlanId'] != 2:
                        with lock:
                            globals()['vmState'][vmId]['vlanId'] = 2
                            globals()['vmState'][vmId]['isid']   = 2
                        update = True
                else:
                    if vmState[vmId]['vlanId'] != 0:
                        with lock:
                            globals()['vmState'][vmId]['vlanId'] = 0
                            globals()['vmState'][vmId]['isid']   = 0
                        update = True
            
            if update:
                with lock:
                    log.debug("push VM status to all WEB clients:\n%s" % json.dumps(vmState,indent=2,sort_keys=True))
                    socketio.emit('state',{'data': json.dumps(vmState)},namespace='/')

        if event.is_set(): break
        if not vmQueue['in'].empty():
            with lock:
                newConfig = vmQueue['in'].get_nowait()
                for vmId in newConfig:
                    if vmId in config['VM']:
                        if config['VM'][vmId]['dhcp']:
                            globals()['config']['VM'][vmId]['ip']  = newConfig[vmId]['ip']
                            globals()['config']['VM'][vmId]['dgw'] = newConfig[vmId]['dgw']
                log.debug("push VM config update to all WEB clients:\n%s" % json.dumps(newConfig,indent=2,sort_keys=True))
                socketio.emit('config',{'data': json.dumps(config['VM'])},namespace='/')

        if event.is_set(): break
        if not vmQueue['state'].empty():
            with lock:
                vmStateData = vmQueue['state'].get_nowait()
                for vmId in vmStateData:
                    globals()['vmState'][vmId]['ip']    = 1      # vmStateData[vmId]['ip']
                    globals()['vmState'][vmId]['dgw']   = vmStateData[vmId]['dgw']
                    globals()['vmState'][vmId]['ping']  = vmStateData[vmId]['ping'].copy()
                    globals()['vmState'][vmId]['mcast'] = vmStateData[vmId]['mcast'].copy()
                log.debug("push VM status to all WEB clients:\n%s" % json.dumps(vmState,indent=2,sort_keys=True))
                socketio.emit('state',{'data': json.dumps(vmState)},namespace='/')

        if event.is_set(): break
        wait = DEFAULT.MAIN_CYCLE - (time.time()-start)
        if wait > 0: socketio.sleep(wait)

    log.debug("leave WEB-Socket background thread")

######################################################################
#                            Tooling                                 #
######################################################################
def debugDisplay(direction, data1, data2) -> None:
    if not DEFAULT.LOG_LEVEL.lower() == 'debug':
        return
        
    if direction == 'inbound':
        if data2:
            inPrint = "\n"+ json.dumps( data2, indent=2 )
        else:
            if data1.data:
                inPrint = "\n"+ str( data1.data ).replace("\\n","\n").replace("\\t","  ")
            else:
                inPrint = ""
        log.debug("WEB inbound %s %s %s %s %s" % (
            data1.remote_addr,
            data1.method,
            data1.path,
            data1.content_type,
            inPrint
        ))
    elif direction == 'outbound':
        log.debug("WEB outbound %s:\n%s" % (data2,json.dumps(data1,indent=2,sort_keys=True )))

######################################################################
def exitHandler() -> None:
    log.debug("exitHandler called")
    lldpDaemon.join()
    log.debug("LLDPd closed")
    vmDaemon.join()
    log.info("\t#####################  STOP vFAD-NG (%s) #####################\n" % __version__)

######################################################################
#                             Main                                   #
######################################################################
signal.signal(signal.SIGABRT,sigHandler)
signal.signal(signal.SIGINT, sigHandler)
signal.signal(signal.SIGTERM,sigHandler)
signal.signal(signal.SIGQUIT,sigHandler)
#signal.signal(signal.SIGCHLD,sigHandler)

log.info("\t##################### START vFAD-NG (%s) #####################" % __version__)

result,config = common.loadConfig()
if result:
    if 'LOG_LEVEL' in config:
        if config['LOG_LEVEL'].lower() == 'debug':
            logHandlers = log.handlers[:]
            for logHandler in logHandlers:
                log.removeHandler(logHandler)
                logHandler.close()
            log = common.setupLogger(config['LOG_LEVEL'].lower())
            logHandlers = log.handlers[:]
    else:
        config['LOG_LEVEL'] = 'INFO'

atexit.register(exitHandler)

nic = VM_NIC_control.getNicData()

dump,lldpState['in'] = common.readFile(DEFAULT.LLDP_FILE)
if lldpState['in']:
    common.deleteFile(DEFAULT.LLDP_FILE)
    if 'expire' in lldpState['in']:
        if lldpState['in']['expire'] < time.time():
            lldpState['in'] = dict()
            log.debug("LLDP cached data expired")
        else:
            log.info("load LLDP data from cache")
    else:
        lldpState['in'] = dict()
else:
    lldpState['in'] = dict()
    log.debug("LLDP no cached data exists")
lldpDaemon = Process(target=lldpChild,args=(event,lldpQueue,))
lldpDaemon.start()

for vmId in config['VM']:
    vmState[vmId] = DEFAULT.VM_STATS.copy()
    for ip in config['VM'][vmId]['ping']:
        vmState[vmId]['ping'][ip] = 0
vmDaemon = Process(target=vmChild,args=(event,vmQueue,))
vmDaemon.start()

#common.setupSignals()

app.config['SECRET_KEY'] = 'secret!'
socketio.on_namespace(webSocketServer('/'))
socketio.start_background_task(target=webSocketBackgroundThread)
socketio.run(
    app,
    host='0.0.0.0',
    port=80,
    debug=False,
)
