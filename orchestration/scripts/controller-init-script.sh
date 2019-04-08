#!/bin/bash
local_ip="$(curl -s http://169.254.169.254/2009-04-04/meta-data/local-ipv4)"
docker run -p 5000:5000 -v /home/ubuntu/.ssh:/root/.ssh -v /var/run/docker.sock:/var/run/docker.sock -d -e LOGGER_HOST="$local_ip" -e LOG_LEVEL="DEBUG" --name orch-controller russanto/bc-orch-controller