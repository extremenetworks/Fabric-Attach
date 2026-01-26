#!/bin/bash

###########################################################################
#
# written by Markus Nikulski
#            markus@nikulski.net
#            created 08. Apr. 2025
#
echo ""
echo "    #########################################"
echo "    ######## vFAD-NG <VERSION> Installer ########"
echo "    #########################################"
echo ""

set -e

################################################################
# Check if the script is run as root
echo "################ check root access ################"
if [[ $EUID -ne 0 ]]; then
  echo ""
  echo "ERROR:    This script must be run as root!" 1>&2
  echo ""
  exit 1
fi

################################################################
# check Hardware and OS type
if [  -n "$(uname -m | grep aarch64)" ]; then
  echo "################ Rasbian is used ################"
  apt update
  DEBIAN_FRONTEND=noninteractive apt -y install bind9-dnsutils
else
  if [  -n "$(uname -a | grep Ubuntu)" ]; then
    echo "################ Ubuntu is used ################"
    apt update
    DEBIAN_FRONTEND=noninteractive apt -y install dnsutils iputils-ping nano python3-pip
  elif [  -n "$(uname -a | grep Debian)" ]; then
    if [ $(lsb_release -a 2> /dev/null | grep Release | awk '{print $2}') == '11' ]; then
      echo "################ Debian 11 is used ################"
      DEBIAN_FRONTEND=noninteractive apt -y install python3-pip
    else
      DEBIAN_VERSION=$(cat /etc/debian_version)
      echo "################ Debian ${DEBIAN_VERSION} is used ################"
    fi
  else
    os=$(uname -a)
    echo ""
    echo "ERROR:    unsupported OS '${os}' found"
    echo ""
    exit 2
  fi
fi

################################################################
# check DNS
echo "################ check DNS ################"
nslookup deb.debian.org
if [ $? -ne 0 ]; then
  echo ""
  echo "ERROR:    DNS doesn't work!"
  echo ""
  exit 3
fi

################################################################
# check Internet access
echo "################ check Internet access ################"
ping -c2 deb.debian.org
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR:    Internet access doesn't work!"
    echo ""
    exit 4
fi

################################################################
# find secondary interface
secondNic="$(ip -brief address show | grep -v -E '([0-9]{1,3}[\\.]){3}[0-9]{1,3}' | awk '{print $1}')"
if [[ -z "$secondNic" ]]; then
  echo ""
  echo "ERROR:    cannot find second NIC interface!"
  echo ""
  exit 5
else
  echo "################ found second NIC interface ${secondNic} ################"
fi

################################################################
# disable IPv6
echo "################ Disable IPv6 ################"
sysctl -w net.ipv6.conf.all.disable_ipv6=1
sysctl -w net.ipv6.conf.default.disable_ipv6=1
sysctl -w net.ipv6.conf.lo.disable_ipv6=1
echo "net.ipv6.conf.all.disable_ipv6 = 1" >> /etc/sysctl.conf

################################################################
# update OS
echo "################ update OS ################"
echo unattended-upgrades unattended-upgrades/enable_auto_updates boolean true | debconf-set-selections
dpkg-reconfigure -f noninteractive unattended-upgrades

apt update
DEBIAN_FRONTEND=noninteractive apt -y full-upgrade
DEBIAN_FRONTEND=noninteractive apt -y autoremove
DEBIAN_FRONTEND=noninteractive apt -y install unattended-upgrades apt-listchanges
cat << 'EOF' > /etc/apt/apt.conf.d/20auto-upgrades
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF


################################################################
# install required software
echo "################ install required software ################"
DEBIAN_FRONTEND=noninteractive apt -y install sudo htop tcpdump snmpd unzip
DEBIAN_FRONTEND=noninteractive apt -y install iperf3
DEBIAN_FRONTEND=noninteractive apt -y install python3-flask python3-flask-socketio python3-eventlet python3-jsonschema python3-psutil python3-waitress
if [  -n "$(uname -a | grep Ubuntu)" ]; then
  pip3 install jsonschema --upgrade
  pip3 install flask --upgrade
  pip3 install flask_socketio --upgrade
elif [ $(lsb_release -a 2> /dev/null | grep Release | awk '{print $2}') == '11' ]; then
  pip3 install jsonschema --upgrade
fi

################################################################
# prep SNMPd
echo "################ prepare SNMP deamon ################"
sed -i "s/Sitting on the Dock of the Bay/LAB/" /etc/snmp/snmpd.conf
sed -i -E "s/agentaddress\s+.+$/agentaddress  0.0.0.0/" /etc/snmp/snmpd.conf
sed -i "s/ -V systemonly//g" /etc/snmp/snmpd.conf
service snmpd restart
systemctl status snmpd

################################################################
# cleanup old vFAD
DESTINATION="/usr/local/vFAD"
if [ -d "$DESTINATION" ]; then
  echo "################ cleanup old vFAD-NG ################"
  systemctl stop vFAD
  systemctl stop LOG-WEB
  rm -rf $DESTINATION/*
  for id in $(ip netns | awk '{print $1}' | awk '{print substr($0, 4)}'); do
    ip netns exec VM-$id ip link set dev VLAN-$id down
    ip netns exec VM-$id ip link set VLAN-$id netns 1
    ip netns delete VM-$id
    ip link delete name VLAN-$id
  done
else
  echo "################ no old vFAD-NG exists ################"
fi

################################################################
# decompress archive
echo "################ decompress vFAD archive ################"
SOURCE=/tmp/vFAD-NG.zip
if [ -f "$SOURCE" ]; then
  echo "INFO: delete old ZIP file"
  rm -f $SOURCE
fi
PAYLOAD_LINE=$(awk '/^__PAYLOAD_BEGINS__/ { print NR + 1; exit 0; }' $0)
tail -n +${PAYLOAD_LINE} $0 | base64 -d | cat > $SOURCE
mkdir -p $DESTINATION
unzip -q -o $SOURCE -d $DESTINATION
rm -rf ${SOURCE}
mv ${DESTINATION}/DEBUG_enable.sh /usr/local/bin/debug
mv ${DESTINATION}/DEBUG_disable.sh /usr/local/bin/info
mv ${DESTINATION}/LOG.sh /usr/local/bin/log
chmod a+x /usr/local/bin/debug
chmod a+x /usr/local/bin/info
chmod a+x /usr/local/bin/log

################################################################
# prep Syslog rotate
echo "################ prepare Syslog rotate ################"
echo "/var/log/vFAD.log {
  rotate 7
  weekly
  compress
  delaycompress
  missingok
  notifempty
}
" > /etc/logrotate.d/vFAD

################################################################
# prep vFAD service
echo "################ prepare vFAD service ################"
echo "[Unit]
Description=vFAD
Wants=networking.service

[Service]
Type=simple
User=root
RemainAfterExit=yes
WorkingDirectory=$DESTINATION
ExecStart=/usr/bin/python3 $DESTINATION/WEB_server.py
ExecReload=/bin/kill -HUP
SyslogIdentifier=vFAD
Restart=on-failure

[Install]
WantedBy=multi-user.target
" > /etc/systemd/system/vFAD.service
systemctl enable vFAD
systemctl daemon-reload
systemctl restart vFAD
systemctl status vFAD

################################################################
# prep WEB-LOG service
echo "INFO: prepare WEB-LOG service ################"
echo "[Unit]
Description=LOG-WEB-Server
Wants=networking.service

[Service]
Type=simple
User=root
RemainAfterExit=yes
WorkingDirectory=$DESTINATION
ExecStart=/usr/bin/python3 $DESTINATION/LOG_server.py
ExecReload=/bin/kill -HUP
Restart=on-failure
StandardOutput=file:/dev/null
StandardError=inherit

[Install]
WantedBy=multi-user.target
" > /etc/systemd/system/LOG-WEB.service
systemctl enable LOG-WEB
systemctl daemon-reload
systemctl restart LOG-WEB
systemctl status LOG-WEB

################################################################
# finish off
echo ""
echo "    ###############################################"
echo "    ########## Installation complete ##############"
echo "    ###############################################"
echo ""
if [ -f /var/run/reboot-required ]; then
    echo "    Please note: Reboot is required!"
    echo ""
fi
exit 0

################################################################
__PAYLOAD_BEGINS__
