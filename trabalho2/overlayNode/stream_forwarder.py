import socket
import struct
import threading
import time
from latency import LatencyManager
from bandwidth import BandwidthHandler

class StreamForwarder:
    def __init__(self, server_socket, latency_manager, max_packet_size=60000):
        self.server_socket = server_socket
        self.latency_manager = latency_manager
        self.max_packet_size = max_packet_size
        self.clients = set()
        self.client_lock = threading.Lock()
        
        # Shared buffer to hold the latest received data
        self.current_data = None
        self.data_lock = threading.Lock()
        
        # Start the background thread to handle control messages and streaming
        self.control_thread = threading.Thread(target=self.handle_control_messages)
        self.control_thread.daemon = True
        self.control_thread.start()

        # Start a thread to receive data from the best server
        self.receiving_thread = threading.Thread(target=self.receive_data_from_best_server)
        self.receiving_thread.daemon = True
        self.receiving_thread.start()

    def handle_control_messages(self):
        """Continuously listen for control messages from connected servers."""
        print("StreamForwarder is listening for control messages...")
        while True:
            try:
                data, addr = self.server_socket.recvfrom(1024)
                message = data.decode().strip().upper()

                if message == "START_STREAM":
                    self.add_client(addr)
                    print(f"Received START request from {addr}. Added to streaming list.")
                elif message == "STOP_STREAM":
                    self.remove_client(addr)
                    print(f"Received STOP request from {addr}. Removed from streaming list.")
                else:
                    self.handle_bandwidth_packet(data, addr)
                    

            except Exception as e:
                print(f"Error handling control message: {e}")

    def handle_bandwidth_packet(self, data, addr):
        """Handle a packet related to bandwidth testing."""
        handler = BandwidthHandler(data, addr, self.server_socket)
        handler.respond()  # Send the response back to the client

    def receive_data_from_best_server(self):
        """Continuously receive data from the server with the best latency."""
        current_best_ip = None
        udp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        while True:
            best_server_ip = self.latency_manager.get_best_server()

            if best_server_ip and best_server_ip != current_best_ip:
                current_best_ip = best_server_ip
                print(f"Switching to the new best server: {current_best_ip}")

            if current_best_ip:
                try:
                    # Request and receive data from the best server
                    udp_client_socket.sendto(b"START_STREAM", (current_best_ip, 12356))
                    data, _ = udp_client_socket.recvfrom(self.max_packet_size)
                    
                    # Store the received data in the shared buffer
                    with self.data_lock:
                        self.current_data = data

                except Exception as e:
                    print(f"Error receiving data from {current_best_ip}: {e}")
                    current_best_ip = None  # Reset to search for a new best server

            time.sleep(10)  # Adjust sleep to avoid excessive looping

    def add_client(self, client_addr):
        """Add a client to the list of active clients."""
        with self.client_lock:
            if client_addr not in self.clients:
                self.clients.add(client_addr)
                print(f"Client {client_addr} added for streaming.")
                threading.Thread(target=self.start_stream, args=(client_addr,), daemon=True).start()

    def remove_client(self, client_addr):
        """Remove a client from the list of active clients."""
        with self.client_lock:
            if client_addr in self.clients:
                self.clients.remove(client_addr)
                print(f"Client {client_addr} removed from streaming.")

    def start_stream(self, client_addr):
        """Continuously send the latest data to a specific client."""
        while client_addr in self.clients:
            with self.data_lock:
                data = self.current_data

            if data:
                print("sent frame")
                self.send_data_to_client(data, client_addr)
            time.sleep(1 / 30)  # Adjust this to match the desired streaming rate

    def send_data_to_client(self, data, client_addr):
        """Send the data to a specific client in chunks, targeting the specified port."""
        data_size = len(data)
        packet_id = 0
        offset = 0

        # Override the port in client_addr with the specified port for streaming
        target_addr = (client_addr[0], self.port)

        while offset < data_size:
            chunk = data[offset:offset + self.max_packet_size - 8]
            chunk_size = len(chunk)
            offset += chunk_size

            # Pack packet_id and data_size into the header
            packet_header = struct.pack('>HI', packet_id, data_size)
            self.server_socket.sendto(packet_header + chunk, target_addr)

            packet_id += 1

    def stop_stream(self, client_addr):
        """Stop streaming to the specified client."""
        print(f"Stopping stream to {client_addr}")
        self.remove_client(client_addr)
