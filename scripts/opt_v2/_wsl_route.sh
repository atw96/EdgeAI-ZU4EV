#!/bin/bash
ip route | head -20
echo ----
ping -c 1 -W 2 ${BOARD_SUBNET:?BOARD_SUBNET}.1 || echo no_gw
ping -c 1 -W 2 ${BOARD_SUBNET:?BOARD_SUBNET}.108 || echo no_host
