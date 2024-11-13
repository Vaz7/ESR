import socket
import struct
import time

class LatencyMonitor:
    def __init__(self, ip, port, shared_dict, data_size=1024, repetitions=5):
        self.ip = ip
        self.port = port
        self.shared_dict = shared_dict 
        self.data_size = data_size
        self.repetitions = repetitions
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.settimeout(2)  # Set a timeout for packet responses

    def measure_latency(self):
        while True:
            times = []

            for _ in range(self.repetitions):
                try:
                    self.client_socket.sendto("LATENCY_REQUEST".encode(), (self.ip, self.port))

                    received_data, _ = self.client_socket.recvfrom(self.data_size)
                    rcv_time = time.time()

                    if received_data.decode() == "NO_DATA":
                        print(f"No latency data available for {self.ip}.")

                    else:
                        latency_sent = received_data.decode().split(",")[0]
                        sent_time = received_data.decode().split(",")[1]
                        sent_time = float(sent_time)

                        latency = (rcv_time - sent_time) * 1000
                        latency += float(latency_sent)

                        times.append(latency)
                
                except socket.timeout:
                    print(f"No response from {self.ip}, packet possibly lost.")

            # Calculate average bandwidth
            if times:
                avg_latency = sum(times) / len(times)
                self.shared_dict[self.ip] = round(avg_latency, 3)
                print(f"Average latency for {self.ip}: {self.shared_dict[self.ip]} Mbps")
            else:
                print(f"No successful transmissions for {self.ip}. Setting latency to inf.")
                self.shared_dict[self.ip] = float("inf")

            # Wait 30 seconds before next measurement
            time.sleep(30)