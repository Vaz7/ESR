import socket
import threading
import time
from bandwidth import BandwidthHandler
from stream import VideoStreamer

class Server:
    def __init__(self, video_path, port=12346, streaming_port=12345, timeout=60):
        self.port = port
        self.timeout = timeout
        self.last_seen = {}  # Dictionary to track the last time each client was seen
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", self.port))  # Bind to all interfaces
        
        # Initialize the VideoStreamer
        self.video_streamer = VideoStreamer(video_path, streaming_port)
        
        # Start a separate thread for the video streaming
        stream_thread = threading.Thread(target=self.video_streamer.start_streaming)
        stream_thread.start()
        
        # Start a thread to monitor inactive clients
        timeout_thread = threading.Thread(target=self.check_inactive_clients)
        timeout_thread.start()

    def start(self):
        print(f"Server listening on UDP port {self.port}")
        while True:
            data, addr = self.server_socket.recvfrom(4096)
            print(f"Received packet from {addr}")
            
            # Update last_seen timestamp for this client
            self.last_seen[addr] = time.time()
            
            # Add the client to the streaming client set if it's not already there
            if addr not in self.video_streamer.clients:
                self.video_streamer.add_client(addr)

            # Handle bandwidth response in a separate thread
            handler_thread = threading.Thread(target=self.handle_client, args=(data, addr))
            handler_thread.start()

    def handle_client(self, data, addr):
        # Create an instance of BandwidthHandler to echo back the received data
        handler = BandwidthHandler(data, addr, self.server_socket)
        handler.respond()  # Send the response back to the client

    def check_inactive_clients(self):
        """Periodically check for clients that have been inactive for more than the timeout period."""
        while True:
            time.sleep(10)  # Check every 10 seconds
            current_time = time.time()
            inactive_clients = []

            # Find inactive clients
            with threading.Lock():
                for addr, last_time in list(self.last_seen.items()):
                    if current_time - last_time > self.timeout:
                        inactive_clients.append(addr)

            # Remove inactive clients from both last_seen and video_streamer
            for client in inactive_clients:
                print(f"Removing inactive client: {client}")
                self.last_seen.pop(client, None)  # Remove from last_seen
                self.video_streamer.remove_client(client)  # Remove from video_streamer
