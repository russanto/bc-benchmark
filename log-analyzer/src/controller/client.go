package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"time"

	"github.com/ethereum/go-ethereum/rpc"
)

// LogEntry represents an entry in the debug.log
type LogEntry struct {
	Timestamp string `json:"timestamp"`
	Verb      string `json:"verb"`
	Block     struct {
		Height int    `json:"height"`
		Hash   string `json:"hash"`
		NTx    int    `json:"nTX"`
		Size   int    `json:"size"`
	} `json:"block"`
	NodeName string `json:"nodeName"`
}

// Verb constants
const (
	BlockMined = "block_mined" // New block mined
	BlockAdded = "block_added" // Block added to chain
)

var quitReader = make(chan os.Signal, 1)

func main() {
	// logFilePath := os.Args[1]
	serverEndpoint := os.Args[1]
	clientName := os.Args[2]

	fmt.Print("Start\n")
	entryChannel := make(chan *LogEntry, 10)
	// fileLog, error := os.Open(logFilePath)
	// if error != nil {
	// 	fmt.Printf("Error opening log file. Exiting...\n")
	// 	return
	// }
	// go reader(bufio.NewReader(fileLog), entryChannel)
	go reader(bufio.NewReader(os.Stdin), entryChannel)
	go sender(serverEndpoint, clientName, entryChannel)
	fmt.Printf("Sending logs to %s \n", serverEndpoint)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt)
	signal.Notify(quitReader, os.Interrupt)

	http.HandleFunc("/fullfil", controllerHandler)
	log.Fatal(http.ListenAndServe(":80", nil))

	for range quit {
		fmt.Print("Ciao\n")
		close(quit)
		close(entryChannel)
	}
}

func reader(reader *bufio.Reader, entryChannel chan *LogEntry) {
	keepReading := true
	var logEntry *LogEntry
	var nextMinedSize int
	for keepReading {
		select {
		case sig := <-quitReader:
			if sig == os.Interrupt {
				keepReading = false
				close(entryChannel)
			}
		default:
			if logEntry == nil {
				logEntry = &LogEntry{}
			}
			text, _ := reader.ReadString('\n')
			lineSlice := strings.Split(text, " ")
			if len(lineSlice) < 6 {
				continue
			}
			logEntry.Timestamp = strings.Join(lineSlice[:2], " ")
			switch lineSlice[2] {
			case "MultiChainMiner:":
				logEntry.Verb = BlockMined
				logEntry.Block.Hash = strings.Split(lineSlice[6], ",")[0]
				logEntry.Block.Height, _ = strconv.Atoi(strings.Split(lineSlice[10], ",")[0])
				logEntry.Block.NTx, _ = strconv.Atoi(lineSlice[12])
				logEntry.Block.Size = nextMinedSize
			case "UpdateTip:":
				logEntry.Verb = BlockAdded
				logEntry.Block.Hash = strings.Split(lineSlice[15], "=")[1]
				logEntry.Block.Height, _ = strconv.Atoi(strings.Split(lineSlice[17], "=")[1])
			case "CreateNewBlock():":
				nextMinedSize, _ = strconv.Atoi(strings.Split(lineSlice[5], "\n")[0])
				fmt.Printf("Size detected %d\n", nextMinedSize)
				continue
			default:
				continue
			}
			entryChannel <- logEntry
			logEntry = nil
		}
	}
}

func sender(url string, clientName string, entryChannel chan *LogEntry) {
	for logEntry := range entryChannel {
		logEntry.NodeName = clientName
		fmt.Printf("%s %s %d\n", logEntry.Timestamp, logEntry.Verb, logEntry.Block.Height)
		logData, _ := json.Marshal(*logEntry)
		_, err := http.Post(url, "application/json", bytes.NewReader(logData))
		if err != nil {
			entryChannel <- logEntry
			time.Sleep(500000000)
		}
	}
}

func controller(nodeHost string) {
	checkerClient, _ := rpc.DialHTTPWithClientAndAuth(fmt.Sprintf("http://%s:7410", nodeHost), new(http.Client), "multichain", "password")
	senderClient, _ := rpc.DialHTTPWithClientAndAuth(fmt.Sprintf("http://%s:7410", nodeHost), new(http.Client), "multichain", "password")

	senderSemaphore := make(chan int, 1)

	go sendTxs(senderClient, 1000, "18pc9Q6DB9t2aBWEEuXZBgQHrEVMWSSKs5DTpi", senderSemaphore)
	go mempoolSizeChecker(checkerClient, 1000, 5, senderSemaphore)
	signalChannel := make(chan os.Signal, 1)
	signal.Notify(signalChannel, os.Interrupt)
	<-signalChannel
	close(senderSemaphore)
}

var controllerHandler = func(w http.ResponseWriter, req *http.Request) {
	go controller(os.Args[3])
}
