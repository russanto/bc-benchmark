FROM golang:alpine as builder
COPY client /go
WORKDIR /go
RUN go build client.go

FROM alpine
COPY --from=builder /go/client /root