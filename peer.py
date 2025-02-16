import socket
import threading
import random
import time
from datetime import datetime

class PeerNode:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.seeds = self.read_config()
        self.peer_list = []
        self.connected_peers = []
        self.message_history = set()
        self.lock = threading.Lock()
        self.running = True

    def read_config(self):
        seeds = []
        with open("config.txt", "r") as f:
            for line in f:
                ip, port = line.strip().split(':')
                seeds.append((ip, int(port)))
        return seeds

    def connect_to_seeds(self):
        selected = random.sample(self.seeds, len(self.seeds)//2 + 1)
        for seed in selected:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(seed)
                sock.send(f"{self.host}:{self.port}".encode())
                data = sock.recv(1024).decode()
                if data != "Empty":
                    self.peer_list.extend(data.split(','))
                sock.close()
            except Exception as e:
                print(f"Failed to connect to seed {seed}: {e}")

    def connect_to_peers(self):
        max_peers = min(4, len(self.peer_list))
        selected = random.sample(self.peer_list, max_peers)
        for peer in selected:
            ip, port = peer.split(':')
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, int(port)))
                self.connected_peers.append(sock)
                sock.send(f"New Connect Request From:{self.host}:{self.port}".encode())
                print(f"Connected to peer {peer}")
            except Exception as e:
                print(f"Failed to connect to peer {peer}: {e}")

    def handle_peer(self, client_socket):
        try:
            while self.running:
                data = client_socket.recv(1024).decode()
                if not data:
                    break

                if data.startswith("Liveness Request"):
                    client_socket.send(f"Liveness Reply:{datetime.now()}:{self.host}:{self.port}".encode())
                elif "GOSSIP" in data:
                    self.handle_gossip(data, client_socket)
        except Exception as e:
            print(f"Peer connection error: {e}")
        finally:
            client_socket.close()

    def handle_gossip(self, message, sender_socket):
        msg_hash = hash(message.split("GOSSIP")[0])
        if msg_hash not in self.message_history:
            self.message_history.add(msg_hash)
            self.write_output(f"Received: {message}")
            self.forward_gossip(message, sender_socket)

    def forward_gossip(self, message, sender_socket):
        with self.lock:
            for peer in self.connected_peers:
                try:
                    if peer != sender_socket:
                        peer.send(message.encode())
                except Exception as e:
                    print(f"Failed to forward gossip: {e}")

    def liveness_check(self):
        while self.running:
            time.sleep(13)
            for peer in self.connected_peers.copy():
                try:
                    peer.send(f"Liveness Request:{datetime.now()}".encode())
                except Exception as e:
                    print(f"Liveness check failed: {e}")
                    self.report_dead_node(peer)

    def report_dead_node(self, peer_socket):
        peer_addr = peer_socket.getpeername()
        dead_msg = f"Dead Node:{peer_addr[0]}:{peer_addr[1]}"
        for seed in self.seeds:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect(seed)
                sock.send(dead_msg.encode())
                sock.close()
            except Exception as e:
                print(f"Failed to report dead node to {seed}: {e}")

    def generate_gossip(self):
        for i in range(10):
            msg = f"{datetime.now()}:{self.host}:{self.port}:GOSSIP{i+1}"
            self.forward_gossip(msg, None)
            time.sleep(5)

    def write_output(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("output_peer.txt", "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def start(self):
        # Start server
        server = threading.Thread(target=self.run_server)
        server.start()

        # Connect to network
        self.connect_to_seeds()
        self.connect_to_peers()

        # Start services
        threading.Thread(target=self.liveness_check).start()
        threading.Thread(target=self.generate_gossip).start()

        server.join()

    def run_server(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        print(f"Peer listening on {self.host}:{self.port}")

        try:
            while self.running:
                client_socket, addr = server_socket.accept()
                threading.Thread(target=self.handle_peer, args=(client_socket,)).start()
        except KeyboardInterrupt:
            self.running = False
            server_socket.close()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python peer.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    peer = PeerNode("127.0.0.1", port)
    peer.start()
