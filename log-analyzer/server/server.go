package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"time"
)

var maxLogEntryPerWorker uint = 2
var initialBlockAllocation = 300
var nodesToWaitBeforePrint = 1

// Node holds information about node partecipating in blockchain network
type Node struct {
	name      string
	ip        string
	lastBlock *Block
}

// LogEntry represents an entry in the debug.log
type LogEntry struct {
	Timestamp string `json:"timestamp"`
	Verb      string `json:"verb"`
	Block     struct {
		Height uint   `json:"height"`
		Hash   string `json:"hash"`
		NTx    uint   `json:"nTX"`
	} `json:"block"`
	NodeName string `json:"nodeName"`
	fromIP   string
}

// Verb constants
const (
	BlockMined = "block_mined" // New block mined
	BlockAdded = "block_added" // Block added to chain
)

func main() {

	logEntryProcessQueue := make(chan *LogEntry, 100)

	logEndpointHandler := func(w http.ResponseWriter, req *http.Request) {
		body, err := ioutil.ReadAll(req.Body)
		defer req.Body.Close()
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}

		var logEntry LogEntry
		err = json.Unmarshal(body, &logEntry)
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		logEntry.fromIP = req.RemoteAddr
		logEntryProcessQueue <- &logEntry
	}

	go sorter(logEntryProcessQueue)

	http.HandleFunc("/", logEndpointHandler)
	fmt.Print("Starting server at port 80\n")
	log.Fatal(http.ListenAndServe(":80", nil))

}

func sorter(processQueue chan *LogEntry) {
	nodesCount := uint(0)
	nodes := make(map[string]chan *LogEntry, 10)
	var currentQueue chan *LogEntry
	for logEntry := range processQueue {
		queue, exists := nodes[logEntry.NodeName]
		if exists {
			queue <- logEntry
		} else {
			if nodesCount%maxLogEntryPerWorker == 0 {
				currentQueue = make(chan *LogEntry)
				go logEntryWorker(currentQueue)
			} else {
				nodes[logEntry.NodeName] = currentQueue
			}
			currentQueue <- logEntry
			nodesCount++
		}
	}
}

func logEntryWorker(processQueue chan *LogEntry) {
	nodes := make(map[string]*Node)
	var node *Node
	var exists bool
	var timestamp time.Time
	for logEntry := range processQueue {
		timestamp, _ = time.Parse("2006-01-02 15:04:05.000", logEntry.Timestamp)
		node, exists = nodes[logEntry.NodeName]
		if !exists {
			node = &Node{
				name: logEntry.NodeName,
				ip:   logEntry.fromIP}
			nodes[logEntry.NodeName] = node
		}
		block, exists := GetBlock(logEntry.Block.Hash)
		switch logEntry.Verb {
		case BlockMined:
			if !exists {
				block = NewBlock(logEntry.Block.Hash, logEntry.Block.Height, node, node.lastBlock, timestamp)
			} else {
				block.miner = node
				// Should manage delay calulation for this case
			}
		case BlockAdded:
			if exists {
				computedDelayQueue <- blockDelayCount{
					block:      block,
					delayCount: block.CalculateDelay(logEntry.NodeName, timestamp)}
			} else {
				block = NewBlock(logEntry.Block.Hash, logEntry.Block.Height, nil, node.lastBlock, timestamp)
			}
			node.lastBlock = block
		}
	}
}

func delayPrinter(delayQueue chan blockDelayCount) {
	for delayCount := range delayQueue {
		if delayCount.delayCount >= nodesToWaitBeforePrint {
			fmt.Printf("Block %d propagated with %d ms of delay\n", delayCount.block.heigth, delayCount.delayCount)
		}
	}
}
