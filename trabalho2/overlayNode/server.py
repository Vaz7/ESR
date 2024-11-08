import socket
import threading
import time
import sys
from latency import LatencyManager
from latency import LatencyHandler
from stream_forwarder import StreamForwarder
class Server:
    
    def __init__(self, port,bootstrapper_IP):
        self.port = port
        self.bootstrapper_IP = bootstrapper_IP
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", self.port))
        

    def start(self):
        print(f"Server listening on UDP port {self.port}")

        print(f"Fetching neighbours from bootstrapper at {self.bootstrapper_IP}")

        listaVizinhos = self.getNeighbours(self.bootstrapper_IP)

        latency_manager = LatencyManager()
        latency_handler = LatencyHandler(port=13333, vizinhos=listaVizinhos, latency_manager=latency_manager)
        latency_handler.start()

        streamForwarder = StreamForwarder(self.server_socket,latency_manager)        
        


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

