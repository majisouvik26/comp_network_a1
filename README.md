# P2P Gossip Protocol Implementation

## Overview
This project implements a peer-to-peer (P2P) gossip protocol with seed and peer nodes. Seed nodes help bootstrap the network by maintaining a list of active peer nodes, while peer nodes:
- Connect to a subset of seeds to get the peer list.
- Connect to other peers to form a network.
- Broadcast gossip messages.
- Check the liveness of connected peers.

## Files
- **config.txt**: Contains the IP addresses and ports of the seed nodes.
- **peer.py**: Implements the peer node functionality.
- **seed.py**: Implements the seed node functionality.
- **Dockerfile**: (Optional) To containerize the application.

## Requirements
- Python 3.x
- Docker

## peer.py

This code implements a peer-to-peer (P2P) networking system where nodes (peers) communicate, exchange peer lists, and propagate messages using a gossip protocol. Each peer connects to a set of seed nodes to register itself and receive a list of other peers. It then establishes connections with selected peers using a Zipf distribution to simulate real-world decentralized networks. The peer node runs a server to handle incoming connections, supports liveness checks via periodic pings, and detects and reports dead nodes. It also generates and forwards gossip messages to propagate information efficiently. The system is multi-threaded, ensuring concurrent handling of connections, messaging, and periodic checks, and logs important events to an output file.

## seed.py
This script implements a **seed node** for a peer-to-peer (P2P) network, responsible for maintaining a list of active peers and facilitating peer discovery. When a new peer connects, the seed node registers it, stores its IP and port, and shares the current peer list. Peers can also report dead nodes, which the seed removes from its list. The seed node handles multiple peer connections using multithreading and logs all significant events in `output_seed.txt`. The server listens on the specified IP (`172.31.77.221`) and a user-defined port, allowing dynamic deployment. The program is designed to be robust, supporting graceful shutdown on keyboard interrupts.

## Running the Application

### Without Docker
1. **Prepare `config.txt`**: Ensure it contains seed node addresses in the format `IP:Port`, e.g.:

127.0.0.1:1500 127.0.0.1:1501 127.0.0.1:1502

2. **Start Seed Nodes**:
Open multiple terminal windows and run:
```bash
python seed.py 1500
python seed.py 1501
python seed.py 1502

    Start Peer Nodes: Open additional terminal windows and run:

    python peer.py 2000
    python peer.py 2001

    Testing:
        Observe the console outputs.
        Check output_seed.txt and output_peer.txt for logs.
        Test liveness by closing a peer node and observing dead node reports.

With Docker

    Build the Docker image:

docker build -t p2p-gossip .

Run the Docker container:

    docker run -it --rm p2p-gossip

    Inside the Container: Start seed and peer nodes as described above.

Code Structure & Comments

    peer.py:
        Reads seeds from config.txt and connects to ⌊(n/2)⌋+1 seeds.
        Retrieves a peer list and connects to a subset of peers.
        Generates and forwards gossip messages while maintaining a message history.
        Periodically sends liveness pings and reports dead nodes.
    seed.py:
        Accepts connections from new peers and maintains a list of active peers.
        Removes dead nodes upon receiving a “Dead Node” message.
    Common Considerations:
        Threading is used for handling multiple connections and background tasks.
        Socket programming is used to simulate the P2P network.

Future Improvements

    Power-Law Degree Distribution:
    Enhance the peer selection algorithm to more closely follow a power-law distribution.
    Modularization:
    Consider refactoring common functions (e.g., logging, configuration parsing) into a separate module.
    Robust Liveness Checking:
    Integrate an actual system ping utility for more reliable liveness checks.

Contributors
- Aditya Sahani(B22CS003)
- Souvik Maji(B22CS089)
