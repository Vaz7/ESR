import threading
import time
import socket
from latency import LatencyMonitor
from stream_rcv import StreamReceiver
from utils import get_and_choose_video

class Client:
    def __init__(self, ip_list, port=13333, stream_port=12346,heartbeat_port=22222):
        self.port = port
        self.stream_port = stream_port
        self.heartbeat_port = heartbeat_port
        self.latency_dict = {}  # Shared dictionary for all IPs' latency measurements
        self.monitors = []  # List to keep track of monitor threads
        self.ip_list = ip_list
        self.current_stream_ip = None
        self.lock = threading.Lock()

        self.wantedVideo = get_and_choose_video(ip_list,13335)

        self.start_monitoring()
        # Initialize a single StreamReceiver to receive data on stream_port
        self.stream_receiver = StreamReceiver(self.stream_port)
        self.stream_thread = threading.Thread(target=self.stream_receiver.start_stream)
        self.stream_thread.start()  # Start the receiver thread once
        threading.Thread(target=self.send_heartbeat).start()  # Start the heartbeat thread

    def validateIpAddress(self):
        for ip in self.ip_list:
            parts = ip.split(".")
            if len(parts) != 4:
                return False
            for part in parts:
                if not part.isdigit():
                    return False
                num = int(part)
                if num < 0 or num > 255:
                    return False
        return True
                                
    def send_heartbeat(self):
        """Periodically send a 'heartbeat' message to the current server via UDP."""
        while True:
            if self.current_stream_ip:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as heartbeat_socket:
                        message = "HEARTBEAT"
                        heartbeat_socket.sendto(message.encode(), (self.current_stream_ip, self.heartbeat_port))
                        #print(f"Sent HEARTBEAT to {self.current_stream_ip}:{self.heartbeat_port} via UDP")
                except Exception as e:
                    print(f"Failed to send 'HEARTBEAT' to {self.current_stream_ip} via UDP. Error: {e}")
            time.sleep(2)  # Send heartbeat every 2 seconds



    def start_monitoring(self):
        if not self.validateIpAddress():
            raise ValueError(f"Invalid IP address in the list")

        for ip in self.ip_list:
            monitor = LatencyMonitor(ip, 13335, self.latency_dict,self.lock)
            self.monitors.append(monitor)

        # Start a thread for each latencyMonitor instance
        for monitor in self.monitors:
            monitor_thread = threading.Thread(target=monitor.measure_latency)
            monitor_thread.start()

        # Start a thread to monitor and switch streams based on latency
        stream_manager_thread = threading.Thread(target=self.manage_stream)
        stream_manager_thread.start()

    def manage_stream(self):
        """Periodically checks latency and switches to the best available stream."""
        while True:
            time.sleep(5)  # Wait 3 seconds to check latency updates
            
            with self.lock:
                # Find the IP with the highest latency
                best_ip = min(self.latency_dict, key=self.latency_dict.get, default=None)
                if best_ip is None:
                    continue
                
                best_latency = self.latency_dict[best_ip]
                #print(f"Best available latency: {best_latency} ms from {best_ip}")

                # Switch to the new stream if it's better than the current one
                if self.current_stream_ip != best_ip:
                    print(f"Switching to the stream from {best_ip}")
                    self.switch_stream(best_ip)

    def switch_stream(self, new_ip):
        """Stop the current stream and start a new one from the given IP."""
        # Stop the current stream from the previous server and notify the server to stop
        if self.current_stream_ip:
            self.send_stop_stream(self.current_stream_ip)

        # Change the target server IP in the existing StreamReceiver
        self.current_stream_ip = new_ip
        self.stream_receiver.set_target_ip(new_ip)  # Set the new server IP

        # Send START_STREAM message to the new server
        self.send_start_stream(new_ip)


    def send_start_stream(self, server_ip):
        """Send a START_STREAM message with the chosen video to the specified server via UDP."""
        if not self.wantedVideo:
            print("No video selected for streaming.")
            return
    
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                message = f"START_STREAM {self.wantedVideo}"
                sock.sendto(message.encode(), (server_ip, self.port))
                print(f"Sent START_STREAM for {self.wantedVideo} to {server_ip}:{self.port} via UDP")
        except Exception as e:
            print(f"Failed to send START_STREAM for {self.wantedVideo} to {server_ip} via UDP. Error: {e}")
    
    def send_stop_stream(self, server_ip):
        """Send a STOP_STREAM message with the chosen video to the specified server via UDP."""
        if not self.wantedVideo:
            print("No video selected for stopping.")
            return
    
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                message = f"STOP_STREAM {self.wantedVideo}"
                sock.sendto(message.encode(), (server_ip, self.port))
                print(f"Sent STOP_STREAM for {self.wantedVideo} to {server_ip}:{self.port} via UDP")
        except Exception as e:
            print(f"Failed to send STOP_STREAM for {self.wantedVideo} to {server_ip} via UDP. Error: {e}")
