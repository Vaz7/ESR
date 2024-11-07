import socket
import threading
import time
from bandwidth import BandwidthHandler
from latency import LatencyHandler
from stream import VideoStreamer
import sys

class Server:
    def __init__(self, video_path, port,bootstrapper_ip):
        self.port = port
        self.bootstrapper_ip = bootstrapper_ip
        self.video_path = video_path
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", self.port))  # Bind to all interfaces
        
        # Initialize the VideoStreamer for handling streaming requests
        self.video_streamer = VideoStreamer(video_path, port)

        vizinhos = self.getNeighbours(bootstrapper_ip)
        print(f"Neighbours are: {vizinhos}")

        latencyHandle = LatencyHandler(13333,vizinhos)
        latencyHandle.start()



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

    def getNeighbours(self, bootstrapper_IP, port=12222):
          try:
              client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
              client_socket.connect((bootstrapper_IP, port))

              message = "Hello, Server!"
              client_socket.send(message.encode())

              response = client_socket.recv(4096)
              response_decoded = response.decode()

              # Neste caso o nodo nao tem vizinhos, mais vale nao estar a gastar letcidade
              if response_decoded == "ERROR":
                  print("No neighbours exist. Exiting program.")
                  client_socket.close()
                  sys.exit(1)

              ip_list = [ip.strip() for ip in response_decoded.split(',')]


              client_socket.close()
              return ip_list

          except Exception as e:
              print(f"Failed to connect to {bootstrapper_IP} on port {port}. Error: {e}")
              sys.exit(1)  # Exit the program on exception
