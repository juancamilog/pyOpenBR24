#!/usr/bin/env sh
#sudo ifconfig eth0 down
#sudo ifconfig eth0 169.254.6.10 netmask 255.255.0.0 up
sudo route add -net 224.0.0.0/4 dev eth0
