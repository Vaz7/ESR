import socket
import threading
import time
import sys
from latency import LatencyManager, LatencyHandler


class OverlayNode:
    def __init__(self, streaming_port, bootstrapper_ip, control_port=13333):
        self.streaming_port = streaming_port
        self.control_port = control_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", streaming_port))

        self.neighbours = self.get_neighbours(bootstrapper_ip, retry_interval=5, max_retries=10)
        print(f"Neighbours are: {self.neighbours}")

        # Shared state for managing streaming
        self.video_client_map = {}  # Maps video names to sets of client IPs
        self.lock = threading.Lock()
        self.current_server = None  # Current best server
        self.last_heartbeat_time = time.time()  # Track last heartbeat timestamp

        # Initialize latency and stream managers
        self.latency_manager = LatencyManager()
        self.latency_handler = LatencyHandler(13334, self.neighbours, self.latency_manager)

    def start(self):
        """Start all overlay node operations in separate threads."""
        print(f"Overlay node listening on UDP port {self.streaming_port}")
        threading.Thread(target=self.latency_handler.start).start()
        threading.Thread(target=self.receive_control_data).start()
        threading.Thread(target=self.retransmit_stream).start()
        threading.Thread(target=self.monitor_and_switch_server).start()
        threading.Thread(target=self.send_heartbeat).start()
        threading.Thread(target=self.receive_heartbeat_requests).start()

    def monitor_and_switch_server(self):
        """Periodically checks for the best server based on latency and switches if necessary."""
        while True:
            time.sleep(10)  # Adjust the interval as needed
            best_server_ip = self.latency_manager.get_best_server()

            with self.lock:
                if best_server_ip and best_server_ip != self.current_server:
                    print(f"Switching to a better server: {best_server_ip}")
                    
                    # Send STOP_STREAM to the current server for all active videos
                    if self.current_server:
                        for video_name in self.video_client_map:
                            self.send_control_command(self.current_server, f"STOP_STREAM {video_name}")

                    # Update the current server and send START_STREAM commands for active videos
                    self.current_server = best_server_ip
                    for video_name in self.video_client_map:
                        if self.video_client_map[video_name]:  # Only if clients are requesting the video
                            self.send_control_command(best_server_ip, f"START_STREAM {video_name}")

    def send_heartbeat(self):
        """Periodically send a 'heartbeat' message to the current server."""
        while True:
            if self.current_server:
                try:
                    heartbeat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    heartbeat_socket.connect((self.current_server, self.control_port))
                    heartbeat_socket.send("HEARTBEAT".encode())  # The heartbeat message
                    heartbeat_socket.close()
                except Exception as e:
                    print(f"Failed to send 'HEARTBEAT' to {self.current_server}. Error: {e}")
            time.sleep(2)  # Send heartbeat every 2 seconds

    def receive_heartbeat_requests(self):
        """Listen for heartbeat messages and reset the client list if no heartbeat is received within 6 seconds."""
        while True:
            try:
                # Check if last heartbeat was received more than 6 seconds ago
                if time.time() - self.last_heartbeat_time > 6:
                    with self.lock:
                        if self.video_client_map:
                            print("Heartbeat timeout! Resetting client list and stopping streams.")
                            self.video_client_map.clear()  # Clear the client list
                            # send STOP_STREAM to the current server for all videos (no caso da ligaçao para o server ser a mesma isto nao adiata, mas still)
                            if self.current_server:
                                for video_name in self.video_client_map:
                                    self.send_control_command(self.current_server, f"STOP_STREAM {video_name}")

                time.sleep(1)  # Check every second

            except Exception as e:
                print(f"Error while checking heartbeat: {e}")

    def receive_control_data(self):
        """Listen for incoming TCP control commands."""
        control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        control_socket.bind(("0.0.0.0", self.control_port))
        control_socket.listen(5)
        print(f"Listening for control data on TCP port {self.control_port}...")

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
                    if len(command_parts) == 2:
                        command = command_parts[0]
                        video_name = command_parts[1]

                        if command == "START_STREAM":
                            self.add_client_to_video(addr[0], video_name)
                        elif command == "STOP_STREAM":
                            self.remove_client_from_video(addr[0], video_name)
                        elif command == "HEARTBEAT":
                            self.last_heartbeat_time = time.time()  # Update last heartbeat timestamp
                            print("tripspsps")
                client_socket.close()
            except Exception as e:
                print(f"Error while handling control data from {addr}: {e}")
                client_socket.close()

    def add_client_to_video(self, client_ip, video_name):
        """Add a client to the list for a specific video and manage start commands."""
        if video_name not in self.video_client_map:
            self.video_client_map[video_name] = set()

        if client_ip not in self.video_client_map[video_name]:
            self.video_client_map[video_name].add(client_ip)
            print(f"Added client {client_ip} to video {video_name}.")

            if len(self.video_client_map[video_name]) == 1:
                # First client for this video, send START_STREAM command to the server
                best_server_ip = self.latency_manager.get_best_server()
                if best_server_ip:
                    self.send_control_command(best_server_ip, f"START_STREAM {video_name}")

    def remove_client_from_video(self, client_ip, video_name):
        """Remove a client from the list for a specific video and manage stop commands."""
        if video_name in self.video_client_map:
            if client_ip in self.video_client_map[video_name]:
                self.video_client_map[video_name].remove(client_ip)
                print(f"Removed client {client_ip} from video {video_name}.")

                if len(self.video_client_map[video_name]) == 0:
                    # Last client for this video, send STOP_STREAM command to the server
                    best_server_ip = self.latency_manager.get_best_server()
                    if best_server_ip:
                        self.send_control_command(best_server_ip, f"STOP_STREAM {video_name}")

    def retransmit_stream(self):
        """Retransmit UDP stream chunks to the clients requesting each video."""
        while True:
            try:
                data, addr = self.server_socket.recvfrom(60000)

                # Extract the video identifier (first 16 bytes)
                video_id_length = 16  # Fixed length of video ID in the header
                video_id = data[:video_id_length].decode('utf-8').strip()  # Decode and strip padding
                with self.lock:
                    if video_id in self.video_client_map:
                        for client_ip in self.video_client_map[video_id]:
                            self.forward_stream_data(client_ip, data)

            except Exception as e:
                print(f"Error during retransmission: {e}")

    def forward_stream_data(self, target_ip, data):
        """Forward the received data to the specified target IP via UDP."""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(data, (target_ip, self.streaming_port))
            client_socket.close()
        except Exception as e:
            print(f"Failed to forward data to {target_ip}. Error: {e}")

    def send_control_command(self, target_ip, command):
        """Send a control command to a specified node."""
        try:
            control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            control_socket.connect((target_ip, self.control_port))
            control_socket.send(command.encode())
            control_socket.close()
            print(f"Sent '{command}' to {target_ip}")
        except Exception as e:
            print(f"Failed to send '{command}' to {target_ip}. Error: {e}")

    def get_neighbours(self, bootstrapper_ip, port=12222, retry_interval=5, max_retries=10):
        """Retrieve a list of neighbor nodes."""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((bootstrapper_ip, port))
            client_socket.send("Hello, Server!".encode())
            response = client_socket.recv(4096).decode()

            if response == "ERROR":
                print("No neighbours found. Exiting.")
                client_socket.close()
                sys.exit(1)

            ip_list = [ip.strip() for ip in response.split(',')]
            client_socket.close()
            return ip_list

        except Exception as e:
            print(f"Failed to connect to {bootstrapper_ip} on port {port}. Error: {e}")
            sys.exit(1)
