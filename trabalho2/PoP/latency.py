import time
import threading
import socket

class LatencyManager:
    def __init__(self):
        self.lock = threading.Lock()  # To ensure thread-safe access
        self.server_latencies = {}  # Dictionary to store latencies for each server
        self.available_videos = None

    def update_latency(self, server_ip, latency, available_videos):
        """Update the latency for a given server."""
        with self.lock:
            self.server_latencies[server_ip] = latency
            self.available_videos = available_videos if latency != float("inf") else "NO_DATA"
            print(f"Updated latency for {server_ip}: {'inf' if latency == float('inf') else f'{latency:.2f} ms'}")

    def get_best_server(self):
        """Get the best latency and its corresponding server IP."""
        with self.lock:
            if not self.server_latencies:
                return None, None, None
            best_server = min(self.server_latencies, key=self.server_latencies.get)
            return best_server, self.server_latencies[best_server], self.available_videos

    def print_latencies(self):
        """Print the current latencies for all tracked servers."""
        with self.lock:
            print("Current latencies for connected servers:")
            for server, latency in self.server_latencies.items():
                print(f"Server {server}: {'inf' if latency == float('inf') else f'{latency:.2f} ms'}")

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
            print(f"Connection established with {addr}")

            try:
                client_socket.settimeout(5)  # Set a timeout for receiving data
                data = client_socket.recv(1024).decode()
                if not data:
                    raise socket.timeout  # Simulate a timeout if no data is received

                # Parse the incoming data (format: "TIMESTAMP,video1,video2,...")
                data_parts = data.split(',', 1)  # Split only once to separate timestamp from video list
                if len(data_parts) < 2:
                    print(f"Invalid data format received from {addr}: {data}")
                    raise ValueError("Invalid data format")

                # Extract and parse timestamp and video list
                sent_time = float(data_parts[0])
                additional_data = data_parts[1]  # This part contains the video list
                received_time = time.time()

                # Calculate latency
                latency = (received_time - sent_time) * 1000  # Convert to milliseconds
                self.latency_manager.update_latency(addr[0], latency, additional_data)

            except (socket.timeout, ValueError) as e:
                print(f"Failed to receive or process data from {addr}. Setting latency to infinity.")
                self.latency_manager.update_latency(addr[0], float("inf"), "NO_DATA")

            except Exception as e:
                print(f"Error while receiving or processing timestamp from {addr}: {e}")

            finally:
                client_socket.close()