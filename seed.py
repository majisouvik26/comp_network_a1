import socket
import threading
from datetime import datetime

class SeedNode:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.peer_list = []
        self.lock = threading.Lock()
        self.running = True

    def handle_peer(self, client_socket, address):
        try:
            while self.running:
                data = client_socket.recv(1024).decode()
                if not data:
                    break

                if data.startswith("Dead Node:"):
                    self.remove_dead_node(data)
                else:
                    parts = data.split(':')
                    if len(parts) >= 2:
                        peer_address = f"{address[0]}:{parts[1]}"
                        with self.lock:
                            if peer_address not in self.peer_list:
                                print(f"New connection from {peer_address}")
                                self.peer_list.append(peer_address)
                            
                            response = ','.join(self.peer_list) if self.peer_list else "Empty"
                            client_socket.send(response.encode())
        except Exception as e:
            print(f"Error handling peer: {e}")
        finally:
            client_socket.close()

    def remove_dead_node(self, data):
        try:
            _, ip, port, *_ = data.split(':')
            dead_node = f"{ip}:{port}"
            with self.lock:
                if dead_node in self.peer_list:
                    self.peer_list.remove(dead_node)
                    print(f"Removed dead node: {dead_node}")
                    self.write_output(f"Removed dead node: {dead_node}")
        except Exception as e:
            print(f"Error removing dead node: {e}")

    def write_output(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("output_seed.txt", "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def start(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(5)
        print(f"Seed node listening on {self.host}:{self.port}")

        try:
            while self.running:
                client_socket, address = server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_peer,
                    args=(client_socket, address)
                )
                thread.start()
        except KeyboardInterrupt:
            self.running = False
            server_socket.close()
            print("Seed node shutdown")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python seed.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    seed = SeedNode("127.0.0.1", port)
    seed.start()
