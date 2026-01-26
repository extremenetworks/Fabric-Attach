#!/usr/bin/env python3

import ctypes, os, sys, platform

osInfo = dict()

if sys.maxsize - 2**64/2 == 0.0:
    osInfo['bitLength'] = 64
elif sys.maxsize - 2**32/2 == 0.0:
    osInfo['bitLength'] = 32
else:
    print("unknown OS bit length: "+ sys.maxsize)
    exit(10)

architecture = platform.machine()
if "arm" in architecture.lower():
    #print("CPU is ARM based, %s bit" % osInfo['bitLength'])
    osInfo['hwType'] = 'arm'
elif "x86" in architecture.lower() or "amd64" in architecture.lower():
    #print("CPU is Intel/AMD based, %s bit" % osInfo['bitLength'])
    osInfo['hwType'] = 'amd'
else:
    print("unknown CPU architecture: "+ architecture)
    exit(10)

fileName = os.getcwd() +'/utilities/hmac_sha-256_%s_%s.so' % (osInfo['hwType'],osInfo['bitLength'])
hmacSha256 = ctypes.cdll.LoadLibrary(os.getcwd() +'/utilities/hmac_sha-256_amd_64.so')

secret = 'Hello World!'.encode("UTF-8")
payload = b'\x08\x80\x00\x00\x00\x0c)\xc7\xb0\x00\x00\x00\x00\xc0'
result = ctypes.c_char_p(hmacSha256.get(secret,len(secret),payload,len(payload))).value.decode("UTF-8")
print(result)
exit(0)