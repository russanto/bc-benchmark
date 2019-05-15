# BC-orchestration
BC-Orchestration is a tool for blockchain deloy and performance analysis. It currently supports Ethereum and Parity for the entire workflow and it is able to deploy Multichain networks.
To apply the workload on the desired blockchain it relies on Hyperledger Caliper. Ethereum isn't supported yet by Caliper and it uses an Ethereum dedicated adapter whose development can be followed at https://github.com/russanto/caliper.

At the moment only Caliper simple benchmark has been ported for Ethereum.

## Usage with docker
With the following commands you will deploy the controller, a listening server on port 5000 will be deployed.  More ways to configure this will be provided in future.
```
docker network create benchmark
docker run -p 5000:5000 -v /home/ubuntu:/root -e SERVER_IP=192.168.20.161 --network benchmark -v /var/run/docker.sock:/var/run/docker.sock -e LOG_LEVEL=INFO --name orch-controller russanto/bc-orch-controller
```
- */home/ubuntu* The user home directory where the necessary ssh key are installed to access target hosts with user ubuntu.
- *SERVER_IP=192.168.20.161* IP at which the controller can be reached by hosts.
- *LOG_LEVEL=INFO* INFO and DEBUG are supported. Logs can be followed launching 'docker logs -f orch-controller'

Hosts need to signal their presence calling the /ready/{server_ip} endpoint. Controller will respond with a single string "understood".

## Endpoints list
### [GET] /ready
Answers with the number of ready hosts available for blockchain deployment
### [GET] /ready/{server_ip}
Notify the controller that the server is ready to host a node
### [POST] /start/geth/{nodes_number}
Starts an Ethereum blockchain using geth. The genesis file must be passed as file in the post request under the 'genesis' key. Both clique and ethash are supported.
### [POST] /start/parity/{nodes_number}
Starts an Ethereum blockchain using parity. The genesis file must be passed as file in the post request under the 'genesis' key. Only PoA is supported.
### [POST] /start/multichain/{nodes_number}/{protocol}
Starts a Multichain blockchain using multichain 2.0.1. The params.dat file must be passed as file in the post request under the 'params' key. Protocol can be either multichain o bitcoin.
### [GET] /stop/{deployment_id}
Stops the blockchain pointed through the deployment_id
### [POST] /benchmark/start/caliper/{deployment_id}
Starts the benchmark on the running Ethereum blockchain pointed by deployment_id. Only simple benchmark is currently supported. Optionally a different configuration of the simple benchmark can be used passing it as file under the 'benchmark' key.
### [GET] /status/{deployment_id}
Return the status of the pointed deployment
