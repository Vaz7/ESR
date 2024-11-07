import time
import threading
import socket

class LatencyHandler:
    def __init__(self, port, vizinhos):
        self.port = port
        self.vizinhos = vizinhos  # Ensure clean IP formatting
        self.server_latencies = {}  # Dictionary to store latencies for each server

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
                self.server_latencies[addr[0]] = latency
                print(f"Received timestamp from {addr[0]}. Calculated latency: {latency:.2f} ms")

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
                client_socket.connect((ip, 13333))  # Assume the same port for neighbors

                # Send the timestamp
                client_socket.send(timestamp.encode())
                print(f"Forwarded timestamp {timestamp} to {ip}")

                # Close the connection
                client_socket.close()

            except socket.timeout:
                print(f"Connection to {ip} timed out after 5 seconds.")
            except Exception as e:
                print(f"Failed to forward message to {ip}. Error: {e}")

            # Adding a slight delay between connections to avoid overwhelming the network
            time.sleep(1)

    def print_server_latencies(self):
        """Print the current latencies for all tracked servers."""
        print("Current latencies for connected servers:")
        for server, latency in self.server_latencies.items():
            print(f"Server {server}: {latency:.2f} ms")
