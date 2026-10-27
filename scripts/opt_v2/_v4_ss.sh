#!/bin/bash
ss -tin dst ${BOARD_IP:?BOARD_IP} || netstat -tn | grep ${BOARD_IP:?BOARD_IP} || true
echo ----
# ssh pid 380 socket stats
ls -l /proc/380/fd 2>/dev/null | head
echo ----
awk '/rchar|wchar/ {print}' /proc/380/io 2>/dev/null || echo no380
date
