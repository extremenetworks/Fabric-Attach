#!/usr/bin/env python3

###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 12. Aug. 2024
#            updated 30. Dec. 2025
#

__version__ = "1.0.1"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import time,threading,logging,subprocess,json,signal,os
from multiprocessing import Event
from flask import Flask,render_template,request,send_from_directory,send_file
from flask_socketio import SocketIO,Namespace
from utilities import DEFAULT

######################################################################
LOG_FILE    = "/var/log/vFAD.log"
LOG_LEVEL   = logging.WARNING                 #  logging.DEBUG  logging.WARNING
MAX_LINE_BUFFER = 2000
DEFAULT_LINE_COUNTER = {'max': MAX_LINE_BUFFER,'all': 0,'error': 0,'warning':0,'info': 0,'debug': 0}

log         = None
event       = Event()
app         = Flask(__name__,static_folder='static')                # WEB server
socketio    = SocketIO(app,async_mode="threading",                   # WEBsocket server (eventlet / gevent / threading)
                        cors_allowed_origins="*")                   # allow CORS (DEVELOPMENT ONLY!)
lock        = threading.Lock()
lineCounter = DEFAULT_LINE_COUNTER.copy()
lineBuffer  = list()
logCleard   = False

#####################################################################
def setupLogger() -> object:
    log = logging.getLogger('LOG-Server')
    log.setLevel(LOG_LEVEL)
    log.propagate = False

    screen = logging.StreamHandler()
    screen.setLevel(LOG_LEVEL)
    screen_formatter = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s', datefmt='%H:%M:%S')
    screen.setFormatter(screen_formatter)
    log.addHandler(screen)
    return log

##################################################################################
def sigHandler(signum, frame) -> None:
    log = logging.getLogger('LOG-Server')
    log.debug("recive Signal %s [%s]", signal.Signals( signum ).name, signum)
    event.set()
    exit(0)

##################################################################################
def setupSignals() -> None:
    signal.signal( signal.SIGABRT, sigHandler )
    signal.signal( signal.SIGINT,  sigHandler )
    signal.signal( signal.SIGTERM, sigHandler )
    signal.signal( signal.SIGQUIT, sigHandler )

######################################################################
#                         WEB-Server                                 #
######################################################################
@app.route('/')
def index() -> None:
    return render_template('log.html', async_mode=socketio.async_mode)

#####################################################################
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path,'static'),'favicon.ico',mimetype='image/vnd.microsoft.icon')

#####################################################################
@app.route('/download')
def downloadFile ():
    if os.path.isfile(DEFAULT.LOG_FILE):
        return send_file(DEFAULT.LOG_FILE,as_attachment=True)

#####################################################################
@app.route('/control',methods=['POST'])
def control() -> None:
    ip = request.environ.get('HTTP_X_REAL_IP',request.remote_addr)
    inbound  = request.get_json(silent=True)
    log.info('WEB-Client %s control %s' % (ip,inbound))

    outbound = dict()
    if 'action' in inbound:
        if inbound['action'] == 'debug':
            outboundReturnCode = 201
            log.info("##################### DEBUG #####################")
            subprocess.Popen("systemctl stop vFAD; sed -i 's/\"LOG_LEVEL\": \"INFO\"/\"LOG_LEVEL\": \"DEBUG\"/g' /etc/vFAD_config.json; systemctl start vFAD",stdin=None,stdout=None,cwd='/',shell=True,text=True)
            outbound['message'] = 'DEBUG Mode'
        elif inbound['action'] == 'info':
            outboundReturnCode = 201
            log.info("##################### INFO #####################")
            subprocess.Popen("systemctl stop vFAD; sed -i 's/\"LOG_LEVEL\": \"DEBUG\"/\"LOG_LEVEL\": \"INFO\"/g' /etc/vFAD_config.json; systemctl start vFAD",stdin=None,stdout=None,cwd='/',shell=True,text=True)
            outbound['message'] = 'INFO Mode'
        elif inbound['action'] == 'clear':
            outboundReturnCode = 201
            log.info("##################### CLEAR LOG #####################")
            outbound['message'] = 'LOG cleared'
            globals()['logCleard'] = True
        else:
            outboundReturnCode = 400
            outbound['message'] = 'Bad Request, unknow action'
            log.warning("unknow action '%s'" % inbound['action'])
    else:
        outboundReturnCode  = 400
        outbound['message'] = 'Bad Request'
        log.warning("control: no action ")

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
    def on_connect(self) -> str:
        ip = request.environ.get('HTTP_X_REAL_IP',request.remote_addr)
        log.info('WEB-Client %s connected' % ip)

    def on_request(self, message):
        ip = request.environ.get('HTTP_X_REAL_IP',request.remote_addr)
        log.debug("Client %s request '%s'" % (ip, message['count']))
        with lock:
            if len(lineBuffer) < message['count']:
                message['count'] = len(lineBuffer)
            counter = 0
            for line in lineBuffer[message['count']:]:
                if event.is_set(): return
                socketio.emit('response',{'data': json.dumps({'msg': line,'counter': lineCounter})})
                counter += 1
            log.debug("WEB-Client %s respond %s messages of %s" % (ip,counter,len(lineBuffer)))

    ##################################################################
    def on_disconnect(self) -> None:
        ip = request.environ.get('HTTP_X_REAL_IP',request.remote_addr)
        log.info('WEB-Client %s disconnected' % ip)

######################################################################
def processLine(inbound: str):
    if inbound is not None and not inbound == '':
        if ' ERROR ' in inbound or ' WARNING ' in inbound or ' INFO ' in inbound or ' DEBUG ' in inbound:
            globals()['lineCounter']['all'] += 1
            if ' ERROR ' in inbound:
                globals()['lineCounter']['error'] += 1
            elif ' WARNING ' in inbound:
                globals()['lineCounter']['warning'] += 1
            elif ' INFO ' in inbound:
                globals()['lineCounter']['info'] += 1
            elif ' DEBUG ' in inbound:
                globals()['lineCounter']['debug'] += 1
            return True,False,inbound
        else:
            return False,False,''
    else:
        time.sleep(0.01)
        return False,False,''

######################################################################
def webSocketBackgroundThread() -> None:
    with open(LOG_FILE,'r') as FH:
        line = ''
        log.info("LOG reader start")
        for newLine in FH.readlines():
            result,wait,line = processLine(newLine)
            if result:
                line = line.replace(' ','&nbsp;').replace('\n','<br>')
                with lock:
                    globals()['lineBuffer'].append(line)
                    if len(lineBuffer) > MAX_LINE_BUFFER:
                        globals()['lineBuffer'].pop(0)
        log.info("LOG reader ready")

        while not event.is_set():
            if logCleard:
                subprocess.Popen("systemctl stop vFAD",stdin=None,stdout=None,cwd='/',shell=True,text=True)
                time.sleep(1)
                line = ''
                globals()['lineBuffer'] = list()
                FH_RW = open(LOG_FILE,'w')
                FH_RW.truncate(0)
                FH_RW.close()
                FH.seek(0)
                globals()['lineCounter'] = DEFAULT_LINE_COUNTER.copy()
                globals()['logCleard'] = False
                subprocess.Popen("systemctl start vFAD",stdin=None,stdout=None,cwd='/',shell=True,text=True)
                log.debug("LOG reader restart")

            result,wait,line = processLine(FH.readline())
            if not wait and result:
                line = line.replace(' ','&nbsp;').replace('\n','<br>')
                with lock:
                    globals()['lineBuffer'].append(line)
                    if len(lineBuffer) > MAX_LINE_BUFFER:
                        globals()['lineBuffer'].pop(0)
                socketio.emit('response',{'data': json.dumps({'msg': line,'counter': lineCounter})})

######################################################################

log = setupLogger()
setupSignals()

app.config['SECRET_KEY'] = 'secret!'
socketio.on_namespace(webSocketServer('/'))
socketio.start_background_task(target=webSocketBackgroundThread)
socketio.run(
    app,
    host='0.0.0.0',
    port=8080,
    debug=False,
    log_output=False,
    allow_unsafe_werkzeug=True
)
