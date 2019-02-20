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
var nodesToWaitBeforePrint = 3

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

	hub := newHub()

	go sorter(logEntryProcessQueue)
	go delayPrinter(computedDelayQueue, hub.broadcast)
	go hub.run()

	http.HandleFunc("/", logEndpointHandler)
	http.HandleFunc("/follow", serveHome)
	http.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		serveWs(hub, w, r)
	})
	fmt.Print("Starting server at port 80\n")
	log.Fatal(http.ListenAndServe(":80", nil))

}

func sorter(processQueue chan *LogEntry) {
	workersCount := 0
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
				workersCount++
				go logEntryWorker(workersCount, currentQueue)
			}
			nodes[logEntry.NodeName] = currentQueue
			currentQueue <- logEntry
			nodesCount++
		}
	}
}

func logEntryWorker(workerID int, processQueue chan *LogEntry) {
	nodes := make(map[string]*Node)
	var node *Node
	var exists bool
	var timestamp time.Time
	for logEntry := range processQueue {
		timestamp, _ = time.Parse("2006-01-02 15:04:05.000", logEntry.Timestamp)

		node, exists = nodes[logEntry.NodeName]
		if !exists {
			fmt.Printf("[Worker %d] Added node %s\n", workerID, logEntry.NodeName)
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
				fmt.Printf("[%s] Block %d: Mined\n", node.name, logEntry.Block.Height)
			} else {
				computedDelayQueue <- blockDelayCount{
					block:      block,
					delayCount: block.SetMiner(node, timestamp)}
				fmt.Printf("[%s] Block %d: Updated miner\n", node.name, logEntry.Block.Height)
			}
		case BlockAdded:
			node.lastBlock = block
			if exists {
				fmt.Printf("[%s] Block %d: Sent update request\n", node.name, logEntry.Block.Height)
				computedDelayQueue <- blockDelayCount{
					block:      block,
					delayCount: block.CalculateDelay(logEntry.NodeName, timestamp)}
			} else {
				block = NewBlock(logEntry.Block.Hash, logEntry.Block.Height, nil, node.lastBlock, timestamp)
				block.CalculateDelay(logEntry.NodeName, timestamp)
				fmt.Printf("[%s] Block %d: Created without miner\n", node.name, logEntry.Block.Height)
			}
		}
	}
}

func delayPrinter(delayQueue chan blockDelayCount, delayAnnounceQueue chan MessageType) {
	for delayCount := range delayQueue {
		if delayCount.delayCount >= nodesToWaitBeforePrint { // Se > allora c'è stato un rollback considerando che nodesToWaitBeforePrint sono tutti
			delays := delayCount.block.GetDelays()
			fmt.Printf("------- Block %d ---------\n", delayCount.block.heigth)
			for key, value := range delays {
				fmt.Printf("- %s: %d\n", key, value/1000000)
			}
			fmt.Printf("-------------------------\n")
			delayAnnounceQueue <- MessageType{
				Height: delayCount.block.Heigth(),
				Delays: delays}
		}
	}
}

func serveHome(w http.ResponseWriter, r *http.Request) {
	log.Println(r.URL)
	if r.URL.Path != "/follow" {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}
	if r.Method != "GET" {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	http.ServeFile(w, r, "home.html")
}
