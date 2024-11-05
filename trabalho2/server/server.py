import socket
import threading
import time
from bandwidth import BandwidthHandler
from stream import VideoStreamer

class Server:
    def __init__(self, video_path, port=12346, streaming_port=12346):
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", self.port))  # Bind to all interfaces
        
        # Initialize the VideoStreamer for handling streaming requests
        self.video_streamer = VideoStreamer(video_path, streaming_port)

    def start(self):
        print(f"Server listening on UDP port {self.port}")
        while True:
            data, addr = self.server_socket.recvfrom(1024)
            
            # Handle START_STREAM and STOP_STREAM messages
            if data == b"START_STREAM":
                print(f"Received START_STREAM from {addr}")
                self.start_stream_for_client(addr)
            elif data == b"STOP_STREAM":
                print(f"Received STOP_STREAM from {addr}")
                self.video_streamer.remove_client(addr)
            else:
                # Handle other data as bandwidth packets
                self.handle_bandwidth_packet(data, addr)

    def start_stream_for_client(self, client_addr):
        """Start streaming to the specified client."""
        # Add the client to the video streamer
        self.video_streamer.add_client(client_addr)
        print(f"Streaming started for client {client_addr}")

    def handle_bandwidth_packet(self, data, addr):
        """Handle a packet related to bandwidth testing."""
        handler = BandwidthHandler(data, addr, self.server_socket)
        handler.respond()  # Send the response back to the client
