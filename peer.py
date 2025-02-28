import socket
import threading
import random
import time
from datetime import datetime
import subprocess
import sys
import numpy as np

class PeerNode:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.seeds = self.read_config()  # list of (ip, port)
        self.seed_connections = []       # persistent connections to seeds
        self.peer_list = []              # union of peers received from seeds (as strings "ip:port")
        self.connected_peers = []        # list of active peer sockets (both outgoing and accepted)
        self.peer_failures = {}          # mapping: peer socket -> consecutive ping failure count
        self.message_history = set()     # store hash values of gossip messages already seen
        self.lock = threading.Lock()
        self.running = True

    def read_config(self):
        seeds = []
        try:
            with open("config.txt", "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        ip, port = line.split(':')
                        seeds.append((ip, int(port)))
        except Exception as e:
            print(f"Error reading config.txt: {e}")
        return seeds

    def connect_to_seeds(self):
        # Select at least ⌊(n/2)⌋ + 1 seeds randomly from the config
        num_to_select = len(self.seeds) // 2 + 1
        selected = random.sample(self.seeds, num_to_select)
        for seed in selected:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(seed)
                # Send registration message (format: "<IP>:<Port>")
                reg_msg = f"{self.host}:{self.port}"
                sock.send(reg_msg.encode())
                # Wait for peer list response from seed
                data = sock.recv(4096).decode()
                if data and data != "Empty":
                    # Expecting comma-separated "ip:port" entries
                    new_peers = data.split(',')
                    with self.lock:
                        self.peer_list.extend(new_peers)
                # Keep the connection open for later reporting (do not close)
                with self.lock:
                    self.seed_connections.append(sock)
                self.write_output(f"Registered with seed {seed} and received peers: {data}")
                print(f"[Peer] Registered with seed {seed} and got peer list: {data}")
            except Exception as e:
                print(f"[Peer] Failed to connect to seed {seed}: {e}")

        # Output the complete union of peer list from seeds
        unique_peers = list(set(self.peer_list))
        self.write_output(f"Complete Peer List from seeds: {unique_peers}")
        print(f"[Peer] Complete Peer List from seeds: {unique_peers}")

    def connect_to_peers(self):
        # Remove self from the list if present
        unique_peers = list(set(self.peer_list))
        unique_peers = [peer for peer in unique_peers if peer != f"{self.host}:{self.port}"]
        if not unique_peers:
            print("[Peer] No other peers available to connect.")
            return

        # To simulate a power-law selection, sort the list and use a Zipf distribution.
        unique_peers.sort()  # arbitrary ordering
        max_peers = min(4, len(unique_peers))
        selected = set()
        while len(selected) < max_peers:
            # Zipf distribution with parameter 2 (values >=1); subtract 1 to get index
            idx = np.random.zipf(2) - 1
            if idx < len(unique_peers):
                selected.add(unique_peers[idx])
        for peer in selected:
            ip, port = peer.split(':')
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, int(port)))
                with self.lock:
                    self.connected_peers.append(sock)
                    self.peer_failures[sock] = 0
                # Send a "New Connect Request" message so that the other peer knows
                conn_msg = f"New Connect Request From:{self.host}:{self.port}"
                sock.send(conn_msg.encode())
                print(f"[Peer] Connected to peer {peer}")
                self.write_output(f"Connected to peer {peer}")
            except Exception as e:
                print(f"[Peer] Failed to connect to peer {peer}: {e}")

    def run_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"[Peer] Listening on {self.host}:{self.port}")
            while self.running:
                client_socket, addr = server_socket.accept()
                # Add incoming connection to connected_peers and initialize failure counter
                with self.lock:
                    self.connected_peers.append(client_socket)
                    self.peer_failures[client_socket] = 0
                threading.Thread(target=self.handle_peer, args=(client_socket, addr), daemon=True).start()
        except Exception as e:
            print(f"[Peer] Server error: {e}")
        finally:
            server_socket.close()

    def handle_peer(self, client_socket, addr=None):
        # This method handles messages arriving on a connection (from another peer)
        peer_addr = addr if addr else client_socket.getpeername()
        try:
            while self.running:
                data = client_socket.recv(4096).decode()
                if not data:
                    break

                # Check for Liveness messages
                if data.startswith("Liveness Request"):
                    # Reply with liveness reply (include timestamp, IP, port)
                    reply = f"Liveness Reply:{datetime.now()}:{self.host}:{self.port}"
                    client_socket.send(reply.encode())
                elif data.startswith("Liveness Reply"):
                    # On receiving a ping reply, reset the failure counter for this socket
                    with self.lock:
                        self.peer_failures[client_socket] = 0
                # Check for gossip messages
                elif "GOSSIP" in data:
                    self.handle_gossip(data, client_socket, peer_addr)
                # (Optional) Handle new connect request from other peers
                elif data.startswith("New Connect Request From:"):
                    # A new peer is connecting to us; log the event.
                    parts = data.split(':')
                    if len(parts) >= 3:
                        new_peer = f"{parts[1]}:{parts[2]}"
                        self.write_output(f"Received connection request from {new_peer}")
                        print(f"[Peer] Received connection request from {new_peer}")
                else:
                    # For other messages, you can add additional handling here.
                    pass
        except Exception as e:
            print(f"[Peer] Error with peer {peer_addr}: {e}")
        finally:
            with self.lock:
                if client_socket in self.connected_peers:
                    self.connected_peers.remove(client_socket)
                if client_socket in self.peer_failures:
                    del self.peer_failures[client_socket]
            client_socket.close()

    def handle_gossip(self, message, sender_socket, sender_addr):
        # Use the part before "GOSSIP" to compute a hash (ignoring the appended Msg# if needed)
        msg_hash = hash(message.split("GOSSIP")[0])
        if msg_hash not in self.message_history:
            self.message_history.add(msg_hash)
            # Log the gossip message with local timestamp and sender's IP
            log_msg = f"Received gossip from {sender_addr[0]}: {message}"
            self.write_output(log_msg)
            print(f"[Peer] {log_msg}")
            self.forward_gossip(message, sender_socket)
        # Otherwise, ignore duplicate messages.

    def forward_gossip(self, message, sender_socket):
        with self.lock:
            for peer in self.connected_peers:
                if peer != sender_socket:
                    try:
                        peer.send(message.encode())
                    except Exception as e:
                        print(f"[Peer] Failed to forward gossip: {e}")

    def liveness_check(self):
        # Every 13 seconds, ping each connected peer using the system ping command.
        while self.running:
            time.sleep(13)
            with self.lock:
                # Work on a copy of the list since we might remove peers.
                peers = list(self.connected_peers)
            for peer in peers:
                try:
                    peer_ip = peer.getpeername()[0]
                    # Use system ping; adjust command as needed for your OS.
                    # For Linux: "ping -c 1 <ip>"
                    result = subprocess.run(["ping", "-c", "1", peer_ip],
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE,
                                            timeout=5)
                    if result.returncode != 0:
                        with self.lock:
                            self.peer_failures[peer] += 1
                            print(f"[Peer] Ping to {peer_ip} failed ({self.peer_failures[peer]} consecutive)")
                            if self.peer_failures[peer] >= 3:
                                self.report_dead_node(peer)
                                self.connected_peers.remove(peer)
                                del self.peer_failures[peer]
                    else:
                        with self.lock:
                            self.peer_failures[peer] = 0
                except Exception as e:
                    with self.lock:
                        self.peer_failures[peer] += 1
                        print(f"[Peer] Exception during ping to {peer_ip}: {e}")
                        if self.peer_failures[peer] >= 3:
                            self.report_dead_node(peer)
                            if peer in self.connected_peers:
                                self.connected_peers.remove(peer)
                            if peer in self.peer_failures:
                                del self.peer_failures[peer]
    
   

    def report_dead_node(self, peer_socket):
        try:
            dead_ip, dead_port = peer_socket.getpeername()
        except Exception:
            return  # Unable to get address
        # Format the dead node message as required:
        # "Dead Node:<DeadNode.IP>:<DeadNode.Port>:<self.timestamp>:<self.IP>"
        timestamp = datetime.now()
        dead_msg = f"Dead Node:{dead_ip}:{dead_port}:{timestamp}:{self.host}"
        # Report to all persistent seed connections
        with self.lock:
            for seed_sock in self.seed_connections:
                try:
                    seed_sock.send(dead_msg.encode())
                except Exception as e:
                    print(f"[Peer] Failed to report dead node to seed: {e}")
        self.write_output(f"Reported dead node {dead_ip}:{dead_port}")
        print(f"[Peer] Reported dead node {dead_ip}:{dead_port}")

    def generate_gossip(self):
        # Generate 10 gossip messages at intervals of 5 seconds.
        for i in range(10):
            # Format: "<timestamp>:<self.IP>:<self.Msg#>"
            msg = f"{datetime.now()}:{self.host}:{self.port}:GOSSIP{i+1}"
            # Log the generated gossip locally
            self.write_output(f"Generated gossip: {msg}")
            print(f"[Peer] Generated gossip: {msg}")
            self.forward_gossip(msg, None)
            time.sleep(5)

    def write_output(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open("output_peer.txt", "a") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"[Peer] Error writing output: {e}")

    def start(self):
        # Start the server thread to accept incoming peer connections.
        server_thread = threading.Thread(target=self.run_server, daemon=True)
        server_thread.start()

        # Connect to seed nodes (persistent connection) and get peer list.
        self.connect_to_seeds()

        # Connect to peers from the received peer list.
        self.connect_to_peers()

        # Start liveness checking and gossip generation in separate threads.
        threading.Thread(target=self.liveness_check, daemon=True).start()
        threading.Thread(target=self.generate_gossip, daemon=True).start()

        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            print("[Peer] Shutting down.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python peer.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    peer = PeerNode("127.0.0.1", port)
    peer.start()
