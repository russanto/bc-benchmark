FROM golang as builder
COPY src/controller /go
WORKDIR /go
RUN go get "github.com/ethereum/go-ethereum/rpc" && cp lib/http.go src/github.com/ethereum/go-ethereum/rpc
RUN go build -o client

FROM debian
COPY --from=builder /go/client /root