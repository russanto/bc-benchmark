export CHAIN_NAME=$1
export SEED_NODE_HOST=$2
export SEED_NODE_PORT=$3
docker-compose -f ./docker-compose/multichain-node.yml -p $CHAIN_NAME up -d