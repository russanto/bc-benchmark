export CHAIN_NAME=$1
export CHAIN_DATADIR=$2
export SEED_NODE_HOST=$3
export SEED_NODE_PORT=$4
docker-compose -f ./docker-compose/multichain-node.yml -p $CHAIN_NAME up -d