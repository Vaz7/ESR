import time
import threading
import socket

class LatencyManager:
    def __init__(self):
        self.lock = threading.Lock()  # To ensure thread-safe access
        self.server_latencies = {}  # Dictionary to store latencies for each server

    def update_latency(self, server_ip, latency):
        """Update the latency for a given server."""
        with self.lock:
            self.server_latencies[server_ip] = latency
            print(f"Updated latency for {server_ip}: {latency:.2f} ms")

    def get_best_server(self):
        """Get the best latency and its corresponding server IP."""
        with self.lock:
            if not self.server_latencies:
                return None, None
            best_server = min(self.server_latencies, key=self.server_latencies.get)
            return best_server, self.server_latencies[best_server]

    def print_latencies(self):
        """Print the current latencies for all tracked servers."""
        with self.lock:
            print("Current latencies for connected servers:")
            for server, latency in self.server_latencies.items():
                print(f"Server {server}: {latency:.2f} ms")

class LatencyHandler:
    def __init__(self, port, vizinhos, latency_manager):
        self.port = port
        self.vizinhos = vizinhos  # Ensure clean IP formatting
        self.latency_manager = latency_manager  # Reference to the LatencyManager instance

    def start(self):
        """Start the thread to receive and forward timestamps."""
        self.latency_thread = threading.Thread(target=self.receive_and_forward_timestamps)
        self.latency_thread.start()

    def receive_and_forward_timestamps(self):
        """Listen for incoming timestamps from multiple servers."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)

        print(f"Client listening for timestamp messages on port {self.port}...")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"Connection established with {addr}")

            try:
                # Receive the timestamp from the server
                data = client_socket.recv(1024).decode()
                if not data:
                    client_socket.close()
                    continue

                received_time = time.time()
                sent_time = float(data)

                # Calculate latency
                latency = (received_time - sent_time) * 1000  # Convert to milliseconds
                self.latency_manager.update_latency(addr[0], latency)

                # Close the connection after receiving the data
                client_socket.close()

                # Forward the received timestamp to all neighbors except the sender
                self.forward_timestamp_to_neighbours(data, addr[0])

            except Exception as e:
                print(f"Error while receiving or processing timestamp from {addr}: {e}")
                client_socket.close()

    def forward_timestamp_to_neighbours(self, timestamp, original_sender):
        """Forward the received timestamp to all neighbors except the original sender."""
        for ip in self.vizinhos:
            if ip == original_sender:
                print(f"Skipping sending timestamp to {ip} (original sender).")
                continue

            try:
                # Create a TCP connection to each neighbor
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.settimeout(5)  # Set a 5-second timeout for the connection attempt
                client_socket.connect((ip, self.port))  # Assume the same port for neighbors

                # Send the timestamp
                client_socket.send(timestamp.encode())
                print(f"Forwarded timestamp to {ip}")

                # Close the connection
                client_socket.close()

            except socket.timeout:
                print(f"Connection to {ip} timed out after 5 seconds.")
            except Exception as e:
                print(f"Failed to forward message to {ip}. Error: {e}")

            # Adding a slight delay between connections to avoid overwhelming the network
            time.sleep(1)

