import socket
import threading
from datetime import datetime
import sys

class SeedNode:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.peer_list = []    # List of registered peers as strings "ip:port"
        self.lock = threading.Lock()
        self.running = True

    def handle_peer(self, client_socket, address):
        try:
            # Continuously handle messages from a connected peer.
            while self.running:
                data = client_socket.recv(4096).decode()
                if not data:
                    break

                if data.startswith("Dead Node:"):
                    self.remove_dead_node(data)
                elif data.startswith("New Connect Request From:"):
                    # Handle connection requests from peers that are not registering
                    parts = data.split(':')
                    if len(parts) >= 3:
                        peer_address = f"{parts[1]}:{parts[2]}"
                        with self.lock:
                            if peer_address not in self.peer_list:
                                self.peer_list.append(peer_address)
                        self.write_output(f"Received new connection request from {peer_address}")
                        print(f"[Seed] Received connection request from {peer_address}")
                    # Send back the current peer list as response
                    with self.lock:
                        response = ','.join(self.peer_list) if self.peer_list else "Empty"
                    client_socket.send(response.encode())
                else:
                    # Assume this is a registration message of the form "<ip>:<port>"
                    parts = data.split(':')
                    if len(parts) >= 2:
                        peer_address = f"{parts[0]}:{parts[1]}"
                        with self.lock:
                            if peer_address not in self.peer_list:
                                self.peer_list.append(peer_address)
                                self.write_output(f"New connection from {peer_address}")
                                print(f"[Seed] New connection from {peer_address}")
                        # Send back the current peer list as response
                        with self.lock:
                            response = ','.join(self.peer_list) if self.peer_list else "Empty"
                        client_socket.send(response.encode())
        except Exception as e:
            print(f"[Seed] Error handling peer {address}: {e}")
        finally:
            client_socket.close()

    def remove_dead_node(self, data):
        try:
            # Expected format: "Dead Node:<DeadNode.IP>:<DeadNode.Port>:<timestamp>:<reporter.IP>"
            parts = data.split(':')
            if len(parts) >= 5:
                dead_node = f"{parts[1]}:{parts[2]}"
                with self.lock:
                    if dead_node in self.peer_list:
                        self.peer_list.remove(dead_node)
                        msg = f"Removed dead node: {dead_node}"
                        self.write_output(msg)
                        print(f"[Seed] {msg}")
        except Exception as e:
            print(f"[Seed] Error removing dead node: {e}")

    def write_output(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open("output_seed.txt", "a") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"[Seed] Error writing output: {e}")

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            print(f"[Seed] Listening on {self.host}:{self.port}")
            while self.running:
                client_socket, address = server_socket.accept()
                threading.Thread(target=self.handle_peer, args=(client_socket, address), daemon=True).start()
        except Exception as e:
            print(f"[Seed] Server error: {e}")
        finally:
            server_socket.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python seed.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    seed = SeedNode("127.0.0.1", port)
    try:
        seed.start()
    except KeyboardInterrupt:
        seed.running = False
        print("[Seed] Shutting down.")
