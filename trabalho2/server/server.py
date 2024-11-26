import socket
import threading
import time
import sys
import os  # Added for extracting file names
from latency import LatencyHandler
from stream import VideoStreamer

class Server:
    def __init__(self, video_paths, bootstrapper_ip, streaming_port=12346, control_port=13333,heartbeat_port=22222):
        # Use original video file names without extensions as the keys
        self.video_paths = {
            os.path.splitext(os.path.basename(path))[0]: path for path in video_paths
        }
        self.streaming_port = streaming_port
        self.control_port = control_port
        self.heartbeat_port = heartbeat_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", streaming_port))

        self.client_heartbeat_map = {}  # Tracks last heartbeat timestamp for each client (global tracking)


        # Initialize the VideoStreamer for each video
        self.video_streamers = {}
        
        for name, path in self.video_paths.items():
            print(f"Initializing VideoStreamer for {name} with path: {path}")
            self.video_streamers[name] = VideoStreamer(path, name, streaming_port)

        self.vizinhos = self.getNeighbours(bootstrapper_ip, retry_interval=5, max_retries=10)
        print(f"Neighbours are: {self.vizinhos}")

        self.latencyHandler = LatencyHandler(13334, self.vizinhos, list(self.video_paths.keys()))

        # Dictionary to map video names to sets of client addresses
        self.stream_active_clients = {video_name: set() for video_name in self.video_paths}
        self.lock = threading.Lock()

        self.latencyHandler.start()

    def start(self):
        print(f"Server listening on UDP port {self.streaming_port}")
        threading.Thread(target=self.receive_control_data).start()
        threading.Thread(target=self.receive_heartbeat_requests).start()
        threading.Thread(target=self.check_client_heartbeats).start()
    
    def receive_control_data(self):
        """Listen for control data via TCP."""
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.bind(("0.0.0.0", self.control_port))
        control_socket.listen(5)
        print(f"Server listening for control data on TCP port {self.control_port}...")

        while True:
            client_socket, addr = control_socket.accept()
            #print(f"Control connection established with {addr}")

            try:
                data = client_socket.recv(1024).decode()
                if not data:
                    client_socket.close()
                    continue
                with self.lock:
                    command_parts = data.split()
                    if command_parts[0] == "START_STREAM" and len(command_parts) == 2:
                        video_name = command_parts[1]
                        if video_name in self.video_streamers:
                            self.stream_active_clients[video_name].add(addr)
                            print(f"Received START_STREAM for {video_name} from {addr}. Added to active clients.")
                            self.start_stream_for_client(addr, video_name)
                        else:
                            print(f"Invalid video name received from {addr}.")

                    elif command_parts[0] == "STOP_STREAM" and len(command_parts) == 2:
                        video_name = command_parts[1]
                        # Check if an entry with the same IP exists
                        matching_clients = [
                            client for client in self.stream_active_clients[video_name]
                            if client[0] == addr[0]
                        ]
                        if matching_clients:
                            for client in matching_clients:
                                self.stream_active_clients[video_name].remove(client)  # Remove matching entries
                            print(f"Received STOP_STREAM for {video_name} from {addr}. Removed from active clients.")
                            self.stop_stream_for_client(addr, video_name)
                        
                client_socket.close()
            except Exception as e:
                print(f"Error while receiving control data from {addr}: {e}")
                client_socket.close()

    def start_stream_for_client(self, client_addr, video_name):
        """Start streaming a specific video to the specified client."""
        self.video_streamers[video_name].add_client(client_addr)
        print(f"Streaming {video_name} started for client {client_addr}")

    def stop_stream_for_client(self, client_addr, video_name):
        """Stop streaming a specific video to the specified client."""
        self.video_streamers[video_name].remove_client(client_addr)
        print(f"Streaming {video_name} stopped for client {client_addr}")


    def receive_heartbeat_requests(self):
        """Listen for heartbeat messages on a separate TCP port."""
        heartbeat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        heartbeat_socket.bind(("0.0.0.0", self.heartbeat_port))
        heartbeat_socket.listen(5)
        heartbeat_socket.settimeout(1)  # Set a timeout for the socket to prevent blocking indefinitely
        print(f"Server listening for heartbeat messages on TCP port {self.heartbeat_port}...")

        while True:
            try:
                client_socket, addr = heartbeat_socket.accept()
                with client_socket:
                    data = client_socket.recv(1024).decode()
                    if data == "HEARTBEAT":
                        with self.lock:
                            self.client_heartbeat_map[addr[0]] = time.time()
                            #print(f"Heartbeat received from client {addr[0]}.")
            except socket.timeout:
                # Timeout reached; loop back to handle timeouts or new connections
                pass
            except Exception as e:
                print(f"Error while handling heartbeat requests: {e}")
    
    def check_client_heartbeats(self):
        """Periodically check client heartbeats and remove stale clients."""
        while True:
            try:
                current_time = time.time()
                stale_clients = []

                with self.lock:
                    # Find stale clients (based only on IP)
                    for client_ip, last_heartbeat in self.client_heartbeat_map.items():
                        if current_time - last_heartbeat > 6:  # 6-second timeout
                            stale_clients.append(client_ip)

                    # Remove stale clients and stop their streams
                    for client_ip in stale_clients:
                        for video_name, clients in self.stream_active_clients.items():
                            # Iterate over the tuples in `clients`
                            for client in list(clients):  # Convert to list to allow removal during iteration
                                if client[0] == client_ip:  # Compare only the IP portion
                                    clients.remove(client)
                                    self.stop_stream_for_client(client, video_name)
                                    print(f"Client {client} removed from video {video_name} due to heartbeat timeout.")
                        del self.client_heartbeat_map[client_ip]  # Remove from heartbeat map

                time.sleep(1)  # Check every second
            except Exception as e:
                print(f"Error while checking client heartbeats: {e}")



    def getNeighbours(self, bootstrapper_IP, port=12222, retry_interval=5, max_retries=None):
        retries = 0
        while True:
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((bootstrapper_IP, port))

                message = "Hello, Server!"
                client_socket.send(message.encode())

                response = client_socket.recv(4096)
                response_decoded = response.decode()

                if response_decoded == "ERROR":
                    print("No neighbours exist. Retrying after a while...")
                    client_socket.close()
                    time.sleep(retry_interval)
                    continue

                ip_list = [ip.strip() for ip in response_decoded.split(',')]
                client_socket.close()
                return ip_list

            except Exception as e:
                print(f"Failed to connect to {bootstrapper_IP} on port {port}. Error: {e}")
                retries += 1
                if max_retries is not None and retries >= max_retries:
                    print("Max retries reached. Exiting program.")
                    sys.exit(1)
                print(f"Retrying after {retry_interval} seconds...")
                time.sleep(retry_interval)
