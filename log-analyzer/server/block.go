package main

import (
	"sync"
	"time"
)

// Block is the block struct info in which we are interested in
type Block struct {
	sync.RWMutex
	previous *Block
	heigth   uint
	hash     string
	nTx      uint
	miner    *Node
	minedAt  time.Time
	delays   map[string]time.Duration
}

type blockDelayCount struct {
	block      *Block
	delayCount int
}

var computedDelayQueue = make(chan blockDelayCount, 100)

var blocks = make(map[string]*Block)
var blocksRWMutex = sync.RWMutex{}

// NewBlock creates a new block and returns its pointer
func NewBlock(hash string, height uint, miner *Node, previous *Block, timestamp time.Time) *Block {
	block := &Block{
		previous: previous,
		hash:     hash,
		heigth:   height,
		miner:    miner,
		minedAt:  timestamp,
		delays:   make(map[string]time.Duration)}
	blocksRWMutex.Lock()
	blocks[hash] = block
	blocksRWMutex.Unlock()
	return block
}

// GetBlock retrieves the block with the given hash
func GetBlock(hash string) (*Block, bool) {
	var block *Block
	var exists bool
	blocksRWMutex.RLock()
	block, exists = blocks[hash]
	blocksRWMutex.RUnlock()
	return block, exists
}

// InitBlock creates a new block and returns its pointer
func (b *Block) InitBlock(hash string, height uint, miner *Node, previous *Block, timestamp time.Time) {
	b.previous = previous
	b.hash = hash
	b.heigth = height
	b.miner = miner
	b.minedAt = timestamp
	b.delays = make(map[string]time.Duration)
	blocksRWMutex.Lock()
	blocks[hash] = b
	blocksRWMutex.Unlock()
}

// CalculateDelay puts the calculcated delay for the given node inside the block. It is thread safe.
func (b *Block) CalculateDelay(nodeIdentifier string, time time.Time) int {
	delay := time.Sub(b.minedAt)
	var computedDelaysCount int
	b.Lock()
	b.delays[nodeIdentifier] = delay
	computedDelaysCount = len(b.delays)
	b.Unlock()
	return computedDelaysCount
}

// GetDelays gets a copy of computed delays of a block. It is Thread Safe.
func (b *Block) GetDelays() map[string]time.Duration {
	delays := make(map[string]time.Duration)
	b.RLock()
	for key, value := range b.delays {
		delays[key] = value
	}
	b.RUnlock()
	return delays
}
