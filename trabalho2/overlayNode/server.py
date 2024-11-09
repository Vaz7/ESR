import socket
import threading
import time
import sys
from latency import LatencyManager
from latency import LatencyHandler
from stream import StreamManager
class Server:
    def __init__(self, streaming_port, bootstrapper_ip, control_port=13333):
        self.streaming_port = streaming_port
        self.control_port = control_port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", streaming_port))
        
        self.vizinhos = self.getNeighbours(bootstrapper_ip, retry_interval=5, max_retries=10)
        print(f"Neighbours are: {self.vizinhos}")

        # Shared state to control the retransmission of the stream
        self.stream_active = False
        self.stream_target = None
        self.lock = threading.Lock()

        # Initialize the LatencyManager, LatencyHandler, and StreamManager
        self.latency_manager = LatencyManager()
        self.latency_handler = LatencyHandler(13333, self.vizinhos, self.latency_manager)
        self.stream_manager = StreamManager(self.latency_manager, self.vizinhos)

        
    def start(self):
        print(f"Middle node server listening on UDP port {self.streaming_port}")
        threading.Thread(target=self.latency_handler.start).start()
        threading.Thread(target=self.stream_manager.check_and_update_stream_path).start()
        threading.Thread(target=self.receive_control_data).start()
        threading.Thread(target=self.retransmit_stream).start()

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
                        self.stream_active = True
                        self.stream_target = addr[0]
                        print(f"Received START_STREAM from {addr}. Stream active set to True.")
                    elif data == "STOP_STREAM" and addr[0] in self.vizinhos:
                        self.stream_active = False
                        self.stream_target = None
                        print(f"Received STOP_STREAM from {addr}. Stream active set to False.")

                client_socket.close()
            except Exception as e:
                print(f"Error while receiving control data from {addr}: {e}")
                client_socket.close()


    def retransmit_stream(self):
        """Retransmit the stream to the current stream target if stream is active."""
        while True:
            with self.lock:
                if self.stream_active and self.stream_target:
                    try:
                        data, addr = self.server_socket.recvfrom(4096)
                        # Forward data to the current stream target via UDP
                        self.forward_stream_data(self.stream_target, data)
                    except Exception as e:
                        print(f"Error during retransmission to {self.stream_target}: {e}")

    
    def forward_stream_data(self, target_ip, data):
        """Forward the received data to the target IP via UDP."""
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(data, (target_ip, self.streaming_port))
            client_socket.close()
            print(f"Forwarded data to {target_ip}")
        except Exception as e:
            print(f"Failed to forward data to {target_ip}. Error: {e}")



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

