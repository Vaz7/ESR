import socket
import threading
import time
from latency import LatencyHandler
from stream import VideoStreamer
import sys

class Server:
    def __init__(self, video_path, bootstrapper_ip, streaming_port=12346, control_port=13333):

        self.video_path = video_path
        self.streaming_port = streaming_port
        self.control_port = control_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", streaming_port))
        
        # Initialize the VideoStreamer for handling streaming requests
        self.video_streamer = VideoStreamer(video_path, streaming_port)

        vizinhos = self.getNeighbours(bootstrapper_ip, retry_interval=5, max_retries=10)
        print(f"Neighbours are: {vizinhos}")

        latencyHandle = LatencyHandler(13334,vizinhos)

        self.stream_active_clients = set()
        self.lock = threading.Lock()

        latencyHandle.start()



    def start(self):
        print(f"Server listening on UDP port {12346}")
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
                    if data == "START_STREAM" and addr[0] in self.vizinhos:
                        self.stream_active_clients.add(addr)
                        print(f"Received START_STREAM from {addr}. Added to active clients.")
                        self.start_stream_for_client(addr)
                    elif data == "STOP_STREAM" and addr in self.stream_active_clients:
                        self.stream_active_clients.remove(addr)
                        print(f"Received STOP_STREAM from {addr}. Removed from active clients.")
                        self.stop_stream_for_client(addr)

                client_socket.close()
            except Exception as e:
                print(f"Error while receiving control data from {addr}: {e}")
                client_socket.close()
                

    def start_stream_for_client(self, client_addr):
        """Start streaming to the specified client."""
        # Add the client to the video streamer
        self.video_streamer.add_client(client_addr)
        print(f"Streaming started for client {client_addr}")
        

    def stop_stream_for_client(self, client_addr):
        """Stop streaming to the specified client."""
        self.video_streamer.remove_client(client_addr)
        print(f"Streaming stopped for client {client_addr}")


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

                # If the node has no neighbors, print a message and retry after a while
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
