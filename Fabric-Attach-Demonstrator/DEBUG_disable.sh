#!/bin/bash

file=/etc/vFAD_config.json

if [ -f $file ]; then
  if grep -q DEBUG /etc/vFAD_config.json; then
    echo "change LOG-LEVEL to INFO"
    sudo systemctl stop vFAD
    sudo sed -i 's/\"LOG_LEVEL\": \"DEBUG\"/\"LOG_LEVEL\": \"INFO\"/g' $file
    sudo systemctl start vFAD
  else
    echo "LOG-LEVEL is alreday INFO"
  fi
else
  echo "Config file $file dosn't exists"
fi
