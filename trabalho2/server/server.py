import socket
import threading
import time
import sys
from latency import LatencyHandler
from stream import VideoStreamer

class Server:
    def __init__(self, video_paths, bootstrapper_ip, streaming_port=12346, control_port=13333):
        self.video_paths = {f"video_{i+1}": path for i, path in enumerate(video_paths)}
        self.streaming_port = streaming_port
        self.control_port = control_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", streaming_port))

        # Initialize the VideoStreamer for each video
        self.video_streamers = {name: VideoStreamer(path, streaming_port) for name, path in self.video_paths.items()}

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

    def receive_control_data(self):
        """Listen for control data via TCP."""
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.bind(("0.0.0.0", self.control_port))
        control_socket.listen(5)
        print(f"Server listening for control data on TCP port {self.control_port}...")

        while True:
            client_socket, addr = control_socket.accept()
            print(f"Control connection established with {addr}")

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
                        if addr in self.stream_active_clients[video_name]:
                            self.stream_active_clients[video_name].remove(addr)
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
