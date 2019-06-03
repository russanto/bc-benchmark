FROM golang:stretch as builder
RUN git clone https://github.com/russanto/block-propagation && mv block-propagation/src/* src/
WORKDIR /go/src/client
RUN go build

FROM debian:stretch
RUN apt-get update && apt-get install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
RUN add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
RUN apt-get update && apt-get install -y docker-ce-cli
COPY start-client.sh /root/
COPY --from=builder /go/src/client/client /root/
WORKDIR /root
ENTRYPOINT [ "/root/start-client.sh" ]