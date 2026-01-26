#!/usr/bin/env python3

###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 26. Oct. 2023
#
#       http://192.168.162.213/
#

__version__ = "1.0.0"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import time,netifaces,waitress
from flask import Flask

###########################################################################
HTML_CODE = """
<HTML>
    <HEAD>
        <TITLE>vFAD-NG VM-<id></TITLE>
    </HEAD>
    <BODY BGCOLOR='11223344'>
        <center>
            <font color='yellow'>
                <strong>
                    <H1>vFAD-NG</H1>
                    <br>
                    <H2>VM-<id></H2>
                </strong>
            </font>
        </center>
    </BODY>
</HTML>
"""

#####################################################################
def getVmId() -> str:
    while True:
        for nic in netifaces.interfaces():
            if nic == 'lo': continue
            if netifaces.AF_INET in netifaces.ifaddresses(nic):
                return nic.replace('VLAN-','')
        time.sleep(1)

#####################################################################

vmId = getVmId()

app = Flask(__name__)

@app.route('/',methods=['GET'])
def index():
    return HTML_CODE.replace('<id>',vmId)

if __name__ == '__main__':
    waitress.serve(app,host="0.0.0.0",port=80)
