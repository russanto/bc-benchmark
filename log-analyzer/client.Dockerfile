FROM golang as builder
COPY src/controller /go
COPY src/github.com /go/src/github.com
WORKDIR /go/src/github.com
RUN cp -r russanto/ ethereum
WORKDIR /go
RUN go build -o client

FROM debian
COPY --from=builder /go/client /root