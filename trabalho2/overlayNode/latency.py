import time
import threading
import socket

class LatencyManager:
    def __init__(self, timeout=15):
        self.lock = threading.Lock()  # Ensure thread-safe access
        self.server_latencies = {}  # Store latencies for each server
        self.server_last_update = {}  # Track last update time for each server
        self.timeout = timeout  # Timeout duration in seconds

    def update_latency(self, server_ip, latency):
        """Update the latency for a given server."""
        with self.lock:
            self.server_latencies[server_ip] = latency
            self.server_last_update[server_ip] = time.time()
            #print(f"Updated latency for {server_ip}: {latency:.2f} ms")

    def get_best_server(self):
        """Get the IP of the server with the lowest latency."""
        with self.lock:
            if not self.server_latencies:
                return None
            # Return the server with the lowest latency that is not marked as infinite
            return min(self.server_latencies, key=self.server_latencies.get)

    def mark_stale_servers(self):
        """Mark servers as inactive if they haven't updated within the timeout period."""
        current_time = time.time()
        with self.lock:
            for server_ip, last_update in list(self.server_last_update.items()):
                if current_time - last_update > self.timeout:
                    print(f"Server {server_ip} is unresponsive. Marking as unreachable.")
                    self.server_latencies[server_ip] = float('inf')

    def print_latencies(self):
        """Print the current latencies for all tracked servers."""
        with self.lock:
            print("Current latencies for connected servers:")
            for server, latency in self.server_latencies.items():
                status = "Unreachable" if latency == float('inf') else f"{latency:.2f} ms"
                print(f"Server {server}: {status}")


class LatencyHandler:
    def __init__(self, port, vizinhos, latency_manager, check_interval=5):
        self.port = port
        self.vizinhos = vizinhos
        self.latency_manager = latency_manager
        self.check_interval = check_interval

    def start(self):
        """Start the thread to handle latency and check inactive servers."""
        self.latency_thread = threading.Thread(target=self.receive_and_forward_timestamps)
        self.latency_thread.start()

        # Start a thread to monitor stale servers
        self.monitor_thread = threading.Thread(target=self.monitor_stale_servers)
        self.monitor_thread.start()

    def receive_and_forward_timestamps(self):
        """Listen for incoming timestamp messages."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(5)
        print(f"Client listening for timestamp messages on port {self.port}...")

        while True:
            client_socket, addr = server_socket.accept()
            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    client_socket.close()
                    continue

                # Parse and update latency
                data_parts = data.split(',', 1)
                if len(data_parts) < 2:
                    print(f"Invalid data format received from {addr}: {data}")
                    client_socket.close()
                    continue

                sent_time = float(data_parts[0])
                received_time = time.time()
                latency = (received_time - sent_time) * 1000  # Convert to milliseconds
                self.latency_manager.update_latency(addr[0], latency)

                # Forward timestamp to neighbors
                self.forward_timestamp_to_neighbours(data, addr[0])
                client_socket.close()

            except Exception as e:
                print(f"Error while receiving or processing timestamp from {addr}: {e}")
                client_socket.close()

    def forward_timestamp_to_neighbours(self, data, original_sender):
        """Forward the received timestamp to all neighbors except the original sender."""
        for ip in self.vizinhos:
            if ip == original_sender:
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
                    client_socket.settimeout(5)
                    client_socket.connect((ip, self.port))
                    client_socket.send(data.encode())
            except Exception as e:
                print(f"Failed to forward message to {ip}. Error: {e}")

    def monitor_stale_servers(self):
        """Periodically check for and mark stale servers."""
        while True:
            self.latency_manager.mark_stale_servers()
            time.sleep(self.check_interval)
