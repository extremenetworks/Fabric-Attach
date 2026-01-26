#!/bin/bash

file=/etc/vFAD_config.json

if [ -f $file ]; then
  if grep -q INFO /etc/vFAD_config.json; then
    echo "change LOG-LEVEL to DEBUG"
    sudo systemctl stop vFAD
    sudo sed -i 's/\"LOG_LEVEL\": \"INFO\"/\"LOG_LEVEL\": \"DEBUG\"/g' $file
    sudo systemctl start vFAD
  else
    echo "LOG-LEVEL is alreday DEBUG"
  fi
else
  echo "Config file $file dosn't exists"
fi
