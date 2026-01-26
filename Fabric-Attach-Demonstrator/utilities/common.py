###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 26. Oct. 2023
#            updated 19.05.2025
#            updated 30.12.2025

__version__ = "1.1.2"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import sys,signal,json,os.path,psutil,copy,hashlib,time
import logging,logging.handlers
from utilities import DEFAULT

log         = None
logLevels   = {
    'critical': logging.CRITICAL,
    'error':    logging.ERROR,
    'warn':     logging.WARNING,
    'warning':  logging.WARNING,
    'info':     logging.INFO,
    'debug':    logging.DEBUG
}

#####################################################################
class LoggerWriter:
    def __init__(self, logfct) -> object:
        self.logfct = logfct
        self.buf = []

    def write(self, msg: str) -> None:
        if msg.endswith('\n'):
            self.buf.append(msg.removesuffix('\n'))
            self.logfct(''.join(self.buf))
            self.buf = []
        else:
            self.buf.append(msg)

    def flush(self) -> None:
        pass

#####################################################################
def setupLogger( logLevel: str = DEFAULT.LOG_LEVEL.lower() ) -> object:
    global log

    log = logging.getLogger('vFAD')
    log.setLevel( logLevels[ logLevel ] )
    log.propagate = False
    sys.stderr = LoggerWriter( log.error )

    logFile = logging.handlers.WatchedFileHandler( DEFAULT.LOG_FILE )
    logFile.setLevel( logLevels[ logLevel ] )
    logFile.setFormatter( logging.Formatter('%(asctime)s %(levelname)-7s [%(filename)s:%(lineno)d] %(message)s') )
    log.addHandler( logFile )

    return log

#####################################################################
def ifDebugLog() -> bool:
    if logging.getLogger('vFAD').level == logging.DEBUG:
        return True
    else:
        return False

##################################################################################
def sigHandler(signum, frame) -> None:
    log = logging.getLogger('vFAD')
    log.debug("recive Signal %s [%s]", signal.Signals( signum ).name, signum)

##################################################################################
def setupSignals() -> None:
    signal.signal( signal.SIGABRT, sigHandler )
    signal.signal( signal.SIGINT,  sigHandler )
    signal.signal( signal.SIGTERM, sigHandler )
    signal.signal( signal.SIGQUIT, sigHandler )
    #signal.signal( signal.SIGHUP,  sigHandler )

##################################################################################
def sendSignal(name: str) -> None:
    for pid in psutil.pids():
        process = psutil.Process( pid )
        if process.name() == name:
            os.kill(pid, signal.SIGUSR1)
            log.debug("found process '%s' [%s]" % (name, pid))
            return
    log.warning("process '%s' not found" % name)

##################################################################################
def readFile(fileName: str, isConfig: bool = False) -> dict:
    if os.path.isfile(fileName) :
        with open(fileName,'r') as FH:
            try:
                config = json.load(FH)
                FH.close()
            except:
                log.error("read file '%s' failed, content is not JSON" % fileName)
                config = copy.deepcopy(DEFAULT.INIT_CONFIG)
                if isConfig:
                    writeConfig(config)
                return False,config
            
            if 'Platform' in config:
                #log.info("Platform given: %s" % config['Platform'])
                if 'Signature' in config:
                    if integrityCheck(config):
                        log.debug("config file %s valid" % fileName)
                        return True,config
                    else:
                        log.warning("config file %s not valid" % fileName)
                else:
                    log.info("integrity check droped, no signature given\n%s" % json.dumps(config,indent=2,sort_keys=True))
                    writeConfig(config)
            else:
                log.debug(f"ignore config '{fileName}' because no Platform given")
                return False,copy.deepcopy(DEFAULT.INIT_CONFIG)
    else:
        config = copy.deepcopy(DEFAULT.INIT_CONFIG)
        if isConfig:
            log.debug("file '%s' not exists" % fileName)
            writeConfig(config)
        return False,config

##################################################################################
def writeFile(fileName: str,data: dict) -> None:
    with open(fileName, 'w') as FH:
        FH.writelines(json.dumps(data,indent=2,sort_keys=True))
        log.debug("write file '%s'" % fileName)

##################################################################################
def deleteFile(fileName: str) -> None:
    if os.path.exists(fileName):
        os.remove(fileName)
        log.debug("delete file '%s'" % fileName)

##################################################################################
def integrityCheck(config: dict) -> bool:
    data = copy.deepcopy(config)
    if 'Signature' in data:
        if 'TimeStamp' in data: del data['TimeStamp']
        sigFile = data['Signature']
        del data['Signature']
        del data['LOG_LEVEL']
        sigComputed = hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        if sigFile == sigComputed:
            log.debug("integrity check passed:\n\tFile: %s\n    computed: %s\n%s" % (
                sigFile,
                sigComputed,
                json.dumps(data,indent=2,sort_keys=True)
            ))
            return True
        else:
            log.warning("integrity check failed:\n\tFile: %s\n    computed: %s\n%s" % (
                sigFile,
                sigComputed,
                json.dumps(data,indent=2,sort_keys=True)
            ))
            return True
    else:
        log.info("integrity check droped, no signature given\n%s" % json.dumps(config,indent=2,sort_keys=True))
        return True
    
######################################################################
def loadConfig(fileName: str = DEFAULT.CONFIG_FILE) -> None:
    result,config = readFile(fileName, True)
    if not "LOG_LEVEL" in config:
        log.info("restore current LOG Level")
        if logging.DEBUG >= logging.root.level:
            config['LOG_LEVEL'] = 'DEBUG'
        else:
            config['LOG_LEVEL'] = 'INFO'
    config['LLDP']['description'] = DEFAULT.LLDP_CONFIG['sysDesc']
    return result,config
    
######################################################################
def writeConfig(config: dict) -> None:
    data = copy.deepcopy(config)
    if 'TimeStamp' in data: del data['TimeStamp']
    if 'Signature' in data: del data['Signature']
    buffer = data['LOG_LEVEL']
    del data['LOG_LEVEL']
    data['Platform'] = DEFAULT.PLATFORM
    data['Version']  = DEFAULT.VERSION
    data['LLDP']['description'] = DEFAULT.LLDP_CONFIG['sysDesc']
    sigComputed = hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
    log.debug("integrity checksum:\n    computed: %s\n%s" % (
        sigComputed,
        json.dumps(data,indent=2,sort_keys=True)
    ))
    data['LOG_LEVEL'] = buffer
    data['TimeStamp'] = time.strftime('%X %x %Z')
    data['Signature'] = sigComputed
    with open(DEFAULT.CONFIG_FILE,'w') as FH:
        FH.writelines(json.dumps(data,indent=2,sort_keys=True))
        log.debug("write config file '%s'" % DEFAULT.CONFIG_FILE)

##################################################################################
