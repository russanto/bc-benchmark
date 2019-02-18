package main

// Node holds information about node partecipating in blockchain network
type Node struct {
	name      string
	ip        string
	lastBlock *Block
}
