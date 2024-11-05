import socket
import struct
import time

class BandwidthMonitor:
    def __init__(self, ip, port, shared_dict, data_size=1024, repetitions=5):
        self.ip = ip
        self.port = port
        self.shared_dict = shared_dict 
        self.data_size = data_size
        self.repetitions = repetitions
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.settimeout(2)  # Set a timeout for packet responses

    def measure_bandwidth(self):
        while True:
            times = []

            for _ in range(self.repetitions):
                try:
                    # Prepare data to send: 4 bytes of size + dummy payload
                    dummy_data = b'x' * self.data_size
                    message = struct.pack('!I', self.data_size) + dummy_data

                    # Record the time before sending
                    start_time = time.time()
                    self.client_socket.sendto(message, (self.ip, self.port))

                    # Wait for response from server
                    received_data, _ = self.client_socket.recvfrom(self.data_size + 4)
                    end_time = time.time()

                    # Check if we received the expected data size
                    if len(received_data) == self.data_size + 4:
                        duration = end_time - start_time
                        times.append(duration)  # Append RTT for this packet
                    else:
                        print(f"Incomplete data from {self.ip}. Expected {self.data_size + 4} bytes, got {len(received_data)} bytes.")
                
                except socket.timeout:
                    print(f"No response from {self.ip}, packet possibly lost.")

            # Calculate average bandwidth
            if times:
                avg_time = sum(times) / len(times)
                bandwidth_mbps = (self.data_size * 8) / (avg_time * 1_000_000)  # Convert bytes to bits, then to Mbps
                self.shared_dict[self.ip] = round(bandwidth_mbps, 3)
                print(f"Average bandwidth for {self.ip}: {self.shared_dict[self.ip]} Mbps")
            else:
                print(f"No successful transmissions for {self.ip}. Setting bandwidth to 0.")
                self.shared_dict[self.ip] = 0  # Indicate no bandwidth measured

            # Wait 30 seconds before next measurement
            time.sleep(30)