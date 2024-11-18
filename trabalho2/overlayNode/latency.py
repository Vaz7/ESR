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
        """Get the IP of the server with the lowest latency."""
        with self.lock:
            if not self.server_latencies:
                return None
            return min(self.server_latencies, key=self.server_latencies.get)

    def print_latencies(self):
        """Print the current latencies for all tracked servers."""
        with self.lock:
            print("Current latencies for connected servers:")
            for server, latency in self.server_latencies.items():
                print(f"Server {server}: {latency:.2f} ms")

class LatencyHandler:
    def __init__(self, port, vizinhos, latency_manager):
        self.port = port
        self.vizinhos = vizinhos
        self.latency_manager = latency_manager

    def start(self):
        """Start the thread to receive and forward timestamps."""
        self.latency_thread = threading.Thread(target=self.receive_and_forward_timestamps)
        self.latency_thread.start()

    def receive_and_forward_timestamps(self):
        """Listen for incoming timestamp messages containing latency and additional data from multiple servers."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)

        print(f"Client listening for timestamp messages on port {self.port}...")

        while True:
            client_socket, addr = server_socket.accept()
            print(f"Connection established with {addr}")

            try:
                # Receive the combined timestamp and additional data from the server
                data = client_socket.recv(1024).decode()
                if not data:
                    client_socket.close()
                    continue
                
                # Parse the incoming data (format: "TIMESTAMP,video1,video2,...")
                data_parts = data.split(',', 1)  # Split only once to separate timestamp from video list
                if len(data_parts) < 2:
                    print(f"Invalid data format received from {addr}: {data}")
                    client_socket.close()
                    continue

                # Extract and parse timestamp and video list
                sent_time = float(data_parts[0])
                received_time = time.time()
                additional_data = data_parts[1]  # This part contains the video list

                # Calculate latency
                latency = (received_time - sent_time) * 1000  # Convert to milliseconds
                self.latency_manager.update_latency(addr[0], latency)

                # Forward the received data (timestamp + video list) to all neighbors except the sender
                self.forward_timestamp_to_neighbours(data, addr[0])

                # Close the connection after receiving and forwarding the data
                client_socket.close()

            except Exception as e:
                print(f"Error while receiving or processing timestamp from {addr}: {e}")
                client_socket.close()

    def forward_timestamp_to_neighbours(self, data, original_sender):
        """Forward the received timestamp and additional data to all neighbors except the original sender."""
        for ip in self.vizinhos:
            if ip == original_sender:
                print(f"Skipping sending timestamp to {ip} (original sender).")
                continue
            
            try:
                # Open a new connection for each neighbor
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                    client_socket.settimeout(5)  # Set a 5-second timeout for the connection attempt
                    client_socket.connect((ip, self.port))
                    client_socket.send(data.encode())
                    print(f"Forwarded timestamp and video list to {ip}")
    
            except (socket.timeout, BrokenPipeError):
                print(f"Connection to {ip} timed out or broken pipe detected.")
            except Exception as e:
                print(f"Failed to forward message to {ip}. Error: {e}")
