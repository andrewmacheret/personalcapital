#!/bin/sh
. $HOME/workspace/personalcapital/.env
$HOME/workspace/personalcapital/get-transactions.py 2>&1 | /usr/local/bin/ts >>$HOME/workspace/personalcapital/get-transactions.log

