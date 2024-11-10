import time
import threading
import socket

class LatencyHandler:
    def __init__(self,port,vizinhos):
        self.port = port
        self.vizinhos = vizinhos

    def start(self):

        self.latency_thread = threading.Thread(target=self.sendLatencyStarter)
        self.latency_thread.start()

    def sendLatencyStarter(self):
        while True:
            for ip in self.vizinhos:
                try:
                    # Create a TCP connection to the client
                    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    client_socket.settimeout(5)  # Set a 5-second timeout for the connection attempt
                    client_socket.connect((ip, self.port))
    
                    # Send a timestamped message to initiate latency calculation
                    timestamp = str(time.time())
                    client_socket.send(timestamp.encode())
                    print(f"Sent latency initiation message to {ip} at {timestamp}")
    
                    # Close the connection
                    client_socket.close()
    
                except socket.timeout:
                    print(f"Connection to {ip} timed out after 5 seconds.")
                except Exception as e:
                    print(f"Failed to send message to {ip}. Error: {e}")
    
            # Wait for 10 seconds before sending the next round of messages
            time.sleep(10)
    