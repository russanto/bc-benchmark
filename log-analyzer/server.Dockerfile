FROM golang as builder
COPY src/server /go
WORKDIR /go
RUN go get github.com/btcsuite/websocket && go build -o server

FROM debian
COPY --from=builder /go/server /go/home.html /root/