package main

import (
	"encoding/hex"
	"fmt"
	"math/rand"
	"time"

	"github.com/ethereum/go-ethereum/rpc"
)

type ResponseGetMempoolInfo struct {
	Size  uint `json:"size"`
	Bytes uint `json:"bytes"`
}

type ResponseSendTransaction string

// func main() {
// 	checkerClient, _ := rpc.Dial("http://192.168.20.139:7410")
// 	senderClient, _ := rpc.Dial("http://192.168.20.139:7410")

// 	senderSemaphore := make(chan int, 1)

// 	go sendTxs(senderClient, 1000, "18pc9Q6DB9t2aBWEEuXZBgQHrEVMWSSKs5DTpi", senderSemaphore)
// 	go mempoolSizeChecker(checkerClient, 1000, 5, senderSemaphore)
// 	signalChannel := make(chan os.Signal, 1)
// 	signal.Notify(signalChannel, os.Interrupt)
// 	<-signalChannel
// 	close(senderSemaphore)
// }

// "1QDR3Vjiq4bJj4ufPVzVdT7R2K5nxxWpL8UMxn"
func sendTxs(client *rpc.Client, n int, addressTo string, semaphore chan int) {
	var result ResponseSendTransaction
	for range semaphore {
		randomGenerator := rand.New(rand.NewSource(int64(time.Now().Nanosecond())))
		txPayload := make([]byte, 4096)
		requests := make([]rpc.BatchElem, n)
		for i := 0; i < n; i++ {
			randomGenerator.Read(txPayload)
			requests[i] = rpc.BatchElem{
				Method: "sendwithdata",
				Args:   []interface{}{addressTo, 0.01, hex.EncodeToString(txPayload)},
				Result: &result}
		}
		error := client.BatchCall(requests)
		if error != nil {
			fmt.Print("[SENDER] Error sending transactions\n")
			fmt.Print(error)
		} else {
			fmt.Printf("[SENDER] Successfully generated and submitted %d transaction\n", n)
		}
	}
}

func mempoolSizeChecker(client *rpc.Client, threshold uint, period uint, sendTxsSemaphore chan int) {
	var response ResponseGetMempoolInfo
	duration := time.Duration(period * 1000000000)
	timer := time.NewTimer(duration)
	for fireTime := range timer.C {
		hour, min, sec := fireTime.Clock()
		fmt.Printf("[MEMPOOL] %d:%d:%d - Checking mempool size\n", hour, min, sec)
		error := client.Call(&response, "getmempoolinfo")
		if error != nil {
			fmt.Print("[MEMPOOL] Error retrieving memory pool information\n")
			return
		}
		if response.Size <= threshold {
			fmt.Printf("[MEMPOOL] Found %d tx - Activating TX sender\n", response.Size)
			sendTxsSemaphore <- 1
		}
		timer.Reset(duration)
	}
}
