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
        self.is_stream_active = False
        self.current_udp_receiver = None  # Node to which we are sending the stream
        self.current_udp_source = None    # Node from which we are requesting the stream
        self.lock = threading.Lock()

        # Initialize latency and stream managers
        self.latency_manager = LatencyManager()
        self.latency_handler = LatencyHandler(13334, self.neighbours, self.latency_manager)

    def start(self):
        """Start all overlay node operations in separate threads."""
        print(f"Overlay node listening on UDP port {self.streaming_port}")
        threading.Thread(target=self.latency_handler.start).start()
        threading.Thread(target=self.periodic_best_node_update).start()
        threading.Thread(target=self.receive_control_data).start()
        threading.Thread(target=self.retransmit_stream).start()
        threading.Thread(target=self.receive_client_latency_request).start()

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
                    if data == "START_STREAM":
                        self.is_stream_active = True
                        self.current_udp_receiver = addr[0]  # Set the UDP receiver to the sender of START_STREAM
                        self.current_udp_source, _ = self.latency_manager.get_best_server()  # Determine the best source
                        print(f"Received START_STREAM from {addr}. UDP receiver set to {self.current_udp_receiver}. Requesting stream from {self.current_udp_source}")
                        self.send_control_command(self.current_udp_source, "START_STREAM")
                    elif data == "STOP_STREAM":
                        if self.is_stream_active:
                            print(f"Received STOP_STREAM from {addr}. Stopping stream to {self.current_udp_receiver}")
                            if self.current_udp_source:
                                self.send_control_command(self.current_udp_source, "STOP_STREAM")
                        self.is_stream_active = False
                        self.current_udp_receiver = None
                        self.current_udp_source = None

                client_socket.close()
            except Exception as e:
                print(f"Error while handling control data from {addr}: {e}")
                client_socket.close()

    def receive_client_latency_request(self):
        """Listen for incoming latency requests from clients."""
        latency_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        latency_socket.bind(("0.0.0.0", 13335))
        print(f"Overlay node listening for latency requests on UDP port {self.port}...")

        while True:
            try:
                data, client_addr = latency_socket.recvfrom(1024)
                if data.decode() == "LATENCY_REQUEST":
                    # Respond with the latency to the best server
                    best_latency, _ = self.latency_manager.get_best_server()
                    current_timestamp = time.time()
                    if best_latency:
                        response = f"{best_latency},{current_timestamp}"
                    else:
                        response = "NO_DATA"
                
                    latency_socket.sendto(response.encode(), client_addr)
                    print(f"Sent latency data to {client_addr}: {response}")
                    
            except Exception as e:
                print(f"Error while handling latency request: {e}")


    def retransmit_stream(self):
        """Retransmit UDP stream chunks to the current UDP receiver."""
        while True:
            with self.lock:
                if self.is_stream_active and self.current_udp_receiver:
                    try:
                        data, addr = self.server_socket.recvfrom(60000)
                        # Forward data to the current receiver
                        self.forward_stream_data(self.current_udp_receiver, data)
                    except Exception as e:
                        print(f"Error during retransmission to {self.current_udp_receiver}: {e}")

    def forward_stream_data(self, target_ip, data):
        """Forward the received data to the specified target IP via UDP."""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(data, (target_ip, self.streaming_port))
            client_socket.close()
        except Exception as e:
            print(f"Failed to forward data to {target_ip}. Error: {e}")

    def periodic_best_node_update(self):
        """Periodically checks for the best node based on latency and updates the UDP source."""
        while True:
            time.sleep(10)  # Adjust interval as needed
            with self.lock:
                if self.is_stream_active:
                    new_udp_source, _ = self.latency_manager.get_best_server()
                    if new_udp_source and new_udp_source != self.current_udp_source:
                        print(f"Better UDP source found: {new_udp_source}. Switching stream source.")
                        # Stop the stream from the current source
                        self.send_control_command(self.current_udp_source, "STOP_STREAM")
                        self.current_udp_source = new_udp_source
                        # Request stream from the new source
                        self.send_control_command(new_udp_source, "START_STREAM")


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

# Usage:
# node = OverlayNode(streaming_port=12345, bootstrapper_ip="192.168.1.1")
# node.start()
