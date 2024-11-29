import time
import threading
import socket

class LatencyManager:
    def __init__(self, timeout=15):
        self.lock = threading.Lock()  # Ensure thread-safe access
        self.server_latencies = {}  # Dictionary to store latencies for each server
        self.last_update_time = {}  # Dictionary to store the last update time for each server
        self.timeout = timeout  # Timeout period in seconds
        self.availableVideos = None

    def update_latency(self, server_ip, latency, availableVideos):
        """Update the latency for a given server."""
        with self.lock:
            self.server_latencies[server_ip] = latency
            self.last_update_time[server_ip] = time.time()  # Record current time for last update
            self.availableVideos = availableVideos
            #print(f"Updated latency for {server_ip}: {latency:.2f} ms")

    def delete_stale_servers(self):
        """Remove servers that haven't updated latency within the timeout period."""
        with self.lock:
            current_time = time.time()
            for server_ip in list(self.server_latencies.keys()):
                if current_time - self.last_update_time[server_ip] > self.timeout:
                    print(f"Removing stale server {server_ip} due to timeout.")
                    del self.server_latencies[server_ip]
                    del self.last_update_time[server_ip]

    def get_best_server(self):
        """Get the best latency and its corresponding server IP."""
        self.delete_stale_servers()  # Ensure stale servers are marked before selecting the best
        with self.lock:
            if not self.server_latencies:
                return None, None, None
            best_server = min(self.server_latencies, key=self.server_latencies.get)
            return best_server, self.server_latencies[best_server], self.availableVideos


    def print_latencies(self):
        """Print the current latencies for all tracked servers."""
        with self.lock:
            print("Current latencies for connected servers:")
            for server, latency in self.server_latencies.items():
                print(f"Server {server}: {latency:.2f} ms")

class LatencyHandler:
    def __init__(self, port, latency_manager):
        self.port = port
        self.latency_manager = latency_manager  # Reference to the LatencyManager instance

    def start(self):
        """Start the thread to receive timestamps."""
        self.latency_thread = threading.Thread(target=self.receive_timestamps)
        self.latency_thread.start()

    def receive_timestamps(self):
        """Listen for incoming timestamp messages containing latency and additional data from multiple servers."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)

        print(f"PoP listening for timestamp messages on port {self.port}...")

        while True:
            client_socket, addr = server_socket.accept()
            #print(f"Connection established with {addr}")
            client_socket.settimeout(5)  # Set timeout for receiving data

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
                additional_data = data_parts[1]  # This part contains the video list
                received_time = time.time()

                # Calculate latency
                latency = (received_time - sent_time) * 1000  # Convert to milliseconds
                self.latency_manager.update_latency(addr[0], latency, additional_data)

                # Close the connection after processing the data
                client_socket.close()

            except socket.timeout:
                print(f"Connection with {addr} timed out. No data received.")
                client_socket.close()
            except ValueError:
                print(f"Failed to parse timestamp from {addr}. Data received: {data}")
                client_socket.close()
            except Exception as e:
                print(f"Error while receiving or processing timestamp from {addr}: {e}")
                client_socket.close()
