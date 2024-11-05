import socket
import threading
from bandwidth import BandwidthHandler

class Server:
    def __init__(self, port=12346):
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind(("0.0.0.0", self.port))  # Bind to all interfaces

    def start(self):
        print(f"Server listening on UDP port {self.port}")
        while True:
            # Receive data from any client
            data, addr = self.server_socket.recvfrom(4096)
            print(f"Received packet from {addr}")

            # Create a new thread to handle the response to the client
            handler_thread = threading.Thread(target=self.handle_client, args=(data, addr))
            handler_thread.start()

    def handle_client(self, data, addr):
        # Create an instance of BandwidthHandler to echo back the received data
        handler = BandwidthHandler(data, addr, self.server_socket)
        handler.respond()  # Send the response back to the client
