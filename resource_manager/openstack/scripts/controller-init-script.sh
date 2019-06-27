#!/bin/bash
local_ip="$(curl -s http://169.254.169.254/2009-04-04/meta-data/local-ipv4)"
docker network create benchmark
docker run -p 3000:5000 --network benchmark -v /home/ubuntu:/root -v /var/run/docker.sock:/var/run/docker.sock -d -e SERVER_IP="$local_ip" -e LOG_LEVEL="INFO" --name orch-controller russanto/bc-orch-controller