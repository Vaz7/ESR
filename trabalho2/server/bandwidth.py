import time

class BandwidthHandler:
    def __init__(self, data, addr, server_socket):
        self.data = data         # Data received from the client
        self.addr = addr         # Client's address (IP, port)
        self.server_socket = server_socket  # Server socket to send the response

    def respond(self):
        try:
            self.server_socket.sendto(self.data, self.addr)
            print(f"Responded to {self.addr} with {len(self.data)} bytes")
        except Exception as e:
            print(f"Error responding to {self.addr}: {e}")
