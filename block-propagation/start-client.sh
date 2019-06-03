#!/bin/bash
export NODE_NAME=$1
export CONTAINER_NAME=$2
export CLIENT=$3
export SERVER=$4
docker logs -f $CONTAINER_NAME 2>&1 | ./client -server $SERVER -name $NODE_NAME $CLIENT