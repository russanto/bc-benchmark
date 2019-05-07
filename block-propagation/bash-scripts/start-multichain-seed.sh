export CHAIN_NAME=$1
export CHAIN_DATADIR=$2
export NODE_NAME=$3
export LOG_COLLECTOR_HOST=$4
export LOG_COLLECTOR_PORT=$5
docker-compose -f ./docker-compose/multichain-seed.yml -p $CHAIN_NAME up -d