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
)

// Block is the block struct info in which we are interested in
type Block struct {
	Heigth int    `json:"height"`
	Hash   string `json:"hash"`
	NTx    int    `json:"nTX"`
}

// LogEntry represents an entry in the debug.log
type LogEntry struct {
	Timestamp string `json:"timestamp"`
	Verb      string `json:"verb"`
	Block     *Block `json:"block"`
	NodeName  string `json:"nodeName"`
}

// Verb constants
const (
	BlockMined = "block_mined" // New block mined
	BlockAdded = "block_added" // Block added to chain
)

var quitReader = make(chan os.Signal, 1)

func main() {
	clientName := os.Args[1]
	serverEndpoint := os.Args[2]

	fmt.Print("Start\n")
	entryChannel := make(chan *LogEntry)
	go reader(bufio.NewReader(os.Stdin), entryChannel)
	go sender(serverEndpoint, clientName, entryChannel)
	fmt.Printf("Sending logs to %s \n", serverEndpoint)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt)
	signal.Notify(quitReader, os.Interrupt)

	for range quit {
		fmt.Print("Ciao\n")
		close(quit)
	}
}

func reader(reader *bufio.Reader, entryChannel chan *LogEntry) {
	keepReading := true
	var logEntry *LogEntry
	for keepReading {
		select {
		case sig := <-quitReader:
			if sig == os.Interrupt {
				keepReading = false
				close(entryChannel)
			}
		default:
			if logEntry == nil {
				logEntry = &LogEntry{Block: &Block{}}
			}
			text, _ := reader.ReadString('\n')
			lineSlice := strings.Split(text, " ")
			logEntry.Timestamp = strings.Join(lineSlice[:2], " ")
			switch lineSlice[2] {
			case "MultiChainMiner:":
				logEntry.Verb = BlockMined
				logEntry.Block.Hash = lineSlice[6]
				logEntry.Block.Heigth, _ = strconv.Atoi(strings.Split(lineSlice[10], ",")[0])
				logEntry.Block.NTx, _ = strconv.Atoi(lineSlice[12])
			case "UpdateTip:":
				logEntry.Verb = BlockAdded
				logEntry.Block.Hash = strings.Split(lineSlice[15], "=")[1]
				logEntry.Block.Heigth, _ = strconv.Atoi(strings.Split(lineSlice[17], "=")[1])
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
		fmt.Printf("%s %d\n", logEntry.Timestamp, logEntry.Block.Heigth)
		logData, _ := json.Marshal(*logEntry)
		_, err := http.Post(url, "application/json", bytes.NewReader(logData))
		if err != nil {
			log.Fatalln(err)
		}
	}
}
