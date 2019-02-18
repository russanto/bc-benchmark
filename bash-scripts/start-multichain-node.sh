export CHAIN_NAME=$1
export CHAIN_DATADIR=$2
export SEED_NODE_HOST=$3
export SEED_NODE_PORT=$4
export NODE_NAME=$5
export LOG_COLLECTOR_HOST=$6
export LOG_COLLECTOR_PORT=$7
docker-compose -f ./docker-compose/multichain-node.yml -p $CHAIN_NAME up -d