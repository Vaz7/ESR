import socket
import threading
import time
from latency import LatencyManager, LatencyHandler

class OverlayNode:
    def __init__(self, streaming_port, control_port=13333, timestamp_port=13334):
        self.streaming_port = streaming_port
        self.control_port = control_port
        self.timestamp_port = timestamp_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", streaming_port))

        # Shared state for managing streaming and client requests
        self.video_client_map = {}  # Maps video names to sets of client IPs
        self.lock = threading.Lock()
        self.current_server = None  # Current source server for the stream

        # Initialize latency manager and handler for timestamp data
        self.latency_manager = LatencyManager()
        self.latency_handler = LatencyHandler(self.timestamp_port, self.latency_manager)

    def start(self):
        """Start all overlay node operations in separate threads."""
        print(f"Overlay node listening on UDP port {self.streaming_port}")
        threading.Thread(target=self.latency_handler.start).start()  # Listen for incoming timestamp data
        threading.Thread(target=self.receive_control_data).start()  # Handle control data from clients
        threading.Thread(target=self.retransmit_stream).start()  # Retransmit video streams
        threading.Thread(target=self.receive_client_latency_request).start()  # Handle client latency requests
        threading.Thread(target=self.monitor_and_switch_server).start()  # Monitor latency and switch servers
        threading.Thread(target=self.send_heartbeat).start()  # Start the heartbeat thread

    def monitor_and_switch_server(self):
        """Periodically checks for the best server based on latency and switches if necessary."""
        while True:
            time.sleep(10)  # Adjust the interval as needed
            best_server_ip, best_latency, _ = self.latency_manager.get_best_server()

            with self.lock:
                if best_server_ip and best_server_ip != self.current_server:
                    print(f"Switching to a better server: {best_server_ip} with latency {best_latency} ms")
                    
                    # Send STOP_STREAM to the current server
                    if self.current_server:
                        for video_name in self.video_client_map:
                            self.send_control_command(self.current_server, f"STOP_STREAM {video_name}")
                    
                    # Update the current server and send START_STREAM commands for active videos
                    self.current_server = best_server_ip
                    for video_name in self.video_client_map:
                        if self.video_client_map[video_name]:
                            self.send_control_command(best_server_ip, f"START_STREAM {video_name}")
    def send_heartbeat(self):
        """Periodically send a 'ole' message to the current server."""
        while True:
            if self.current_server:
                try:
                    heartbeat_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    heartbeat_socket.connect((self.current_server, self.control_port))
                    heartbeat_socket.send("HEARTBEAT".encode())
                    heartbeat_socket.close()
                    print(f"Sent HEARTBEAT to {self.current_server}")
                except Exception as e:
                    print(f"Failed to send 'HEARTBEAT' to {self.current_server}. Error: {e}")
            time.sleep(2)  


    def receive_control_data(self):
        """Listen for incoming TCP control commands from clients."""
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

                client_socket.close()
            except Exception as e:
                print(f"Error while handling control data from {addr}: {e}")
                client_socket.close()

    def add_client_to_video(self, client_ip, video_name):
        """Add a client to the list for a specific video and send start command if necessary."""
        if video_name not in self.video_client_map:
            self.video_client_map[video_name] = set()

        if client_ip not in self.video_client_map[video_name]:
            self.video_client_map[video_name].add(client_ip)
            print(f"Added client {client_ip} to video {video_name}.")

            if len(self.video_client_map[video_name]) == 1 and self.current_server:
                # First client requesting this video, send START_STREAM command upstream
                self.send_control_command(self.current_server, f"START_STREAM {video_name}")

    def remove_client_from_video(self, client_ip, video_name):
        """Remove a client from the list for a specific video and send stop command if necessary."""
        if video_name in self.video_client_map and client_ip in self.video_client_map[video_name]:
            self.video_client_map[video_name].remove(client_ip)
            print(f"Removed client {client_ip} from video {video_name}.")

            if len(self.video_client_map[video_name]) == 0 and self.current_server:
                # No more clients requesting this video, send STOP_STREAM command upstream
                self.send_control_command(self.current_server, f"STOP_STREAM {video_name}")

    def retransmit_stream(self):
        """Retransmit UDP stream chunks only to the clients requesting the specific video."""
        while True:
            try:
                data, addr = self.server_socket.recvfrom(60000)

                # Extract the video identifier from the packet header (first 16 bytes)
                video_id_length = 16  # Fixed length of video ID in the header
                video_id = data[:video_id_length].decode().strip()

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

    def receive_client_latency_request(self):
        """Listen for incoming latency requests from clients."""
        latency_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        latency_socket.bind(("0.0.0.0", 13335))
        print(f"Overlay node listening for latency requests on UDP port {13335}...")

        while True:
            try:
                data, client_addr = latency_socket.recvfrom(1024)
                if data.decode() == "LATENCY_REQUEST":
                    # Respond with the latency and available videos from the best server
                    _, best_latency, available_videos = self.latency_manager.get_best_server()
                    current_timestamp = time.time()
                    if best_latency:
                        response = f"{best_latency},{current_timestamp},{available_videos}"
                    else:
                        response = "NO_DATA"

                    latency_socket.sendto(response.encode(), client_addr)
                    #print(f"Sent latency data to {client_addr}: {response}")

            except Exception as e:
                print(f"Error while handling latency request: {e}")
