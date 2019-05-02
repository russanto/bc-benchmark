FROM debian:latest as builder
WORKDIR /root
RUN apt-get update && apt-get install -y wget
RUN wget https://www.multichain.com/download/multichain-2.0.1.tar.gz && tar -xvzf multichain-2.0.1.tar.gz
WORKDIR /root/multichain-2.0.1

FROM debian:latest
COPY --from=builder /root/multichain-2.0.1/multichaind /root/multichain-2.0.1/multichain-cli /root/multichain-2.0.1/multichain-util /usr/local/bin/