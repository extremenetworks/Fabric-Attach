#!/bin/bash

file=/var/log/vFAD.log

if [ -f $file ]; then
  tail -n 1000 -f /var/log/vFAD.log
else
  echo "LOG file $file dosn't exists"
fi
