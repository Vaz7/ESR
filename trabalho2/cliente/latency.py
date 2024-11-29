import socket
import struct
import time

class LatencyMonitor:
    def __init__(self, ip, port, shared_dict,lock, data_size=1024, repetitions=2):
        self.ip = ip
        self.port = port
        self.shared_dict = shared_dict 
        self.data_size = data_size
        self.lock = lock
        self.repetitions = repetitions
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.settimeout(2)  # Set a timeout for packet responses
            
    def measure_latency(self):
        # Set the socket timeout to 5 seconds to wait for a response
        self.client_socket.settimeout(5)
    
        while True:
            times = []
            attempts = 0  # Counter to track the number of attempts
    
            while attempts < self.repetitions:
                try:
                    # Send a latency request
                    self.client_socket.sendto("LATENCY_REQUEST".encode(), (self.ip, self.port))
                    attempts += 1  # Count this as an attempt
                    
                    try:
                        # Wait for a response within the timeout period
                        received_data, _ = self.client_socket.recvfrom(self.data_size)
                        rcv_time = time.time()
    
                        # Parse received data and calculate latency
                        if received_data.decode() == "NO_DATA":
                            print(f"No latency data available for {self.ip}.")
                        else:
                            #print(f"rcvd_data: {received_data}")
                            parts = received_data.decode().split(",")
                            # porque as mensagens vao sempre conter pelo menos timestamp,latencia,video1....
                            if len(parts) <3:
                                print(f"Unexpected data format from {self.ip}: {received_data.decode()}")
                                continue
                            
                            latency_sent = parts[0] 
                            sent_time = parts[1]
                            sent_time = float(sent_time)
    
                            latency = (rcv_time - sent_time) * 1000  # Convert to milliseconds
                            latency += float(latency_sent)
    
                            times.append(latency)
    
                    except socket.timeout:
                        print(f"No response from {self.ip} within 5 seconds, sending another packet.")
    
                except Exception as e:
                    print(f"Error during sending or receiving: {e}")
    
            # Calculate average latency if there were successful transmissions
            if times:
                avg_latency = sum(times) / len(times)
                with self.lock:
                    self.shared_dict[self.ip] = round(avg_latency, 3)
                #print(f"Average latency for {self.ip}: {self.shared_dict[self.ip]} ms")
            else:
                print(f"No successful transmissions for {self.ip}. Setting latency to inf.")
                with self.lock:
                    self.shared_dict[self.ip] = float("inf")
    
            # Wait 30 seconds before the next full measurement cycle
            time.sleep(10)
    