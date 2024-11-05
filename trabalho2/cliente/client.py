import threading
import time
import socket
from bandwidth import BandwidthMonitor
from stream_rcv import StreamReceiver

class Client:
    def __init__(self, ip_list, port=12346, stream_port=12346):
        self.port = port
        self.stream_port = stream_port
        self.bandwidth_dict = {}  # Shared dictionary for all IPs' bandwidth measurements
        self.monitors = []  # List to keep track of monitor threads
        self.ip_list = ip_list
        self.current_stream_receiver = None
        self.current_stream_ip = None
        self.lock = threading.Lock()

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
    
    def start_monitoring(self):
        if not self.validateIpAddress():
            raise ValueError(f"Invalid IP address in the list")

        for ip in self.ip_list:
            monitor = BandwidthMonitor(ip, self.port, self.bandwidth_dict)
            self.monitors.append(monitor)

        # Start a thread for each BandwidthMonitor instance
        for monitor in self.monitors:
            monitor_thread = threading.Thread(target=monitor.measure_bandwidth)
            monitor_thread.start()

        # Start a thread to monitor and switch streams based on bandwidth
        stream_manager_thread = threading.Thread(target=self.manage_stream)
        stream_manager_thread.start()

    def manage_stream(self):
        """Periodically checks bandwidth and switches to the best available stream."""
        while True:
            time.sleep(3)  # Wait 3 seconds to check bandwidth updates
            
            with self.lock:
                # Find the IP with the highest bandwidth
                best_ip = max(self.bandwidth_dict, key=self.bandwidth_dict.get, default=None)
                if best_ip is None:
                    continue
                
                best_bandwidth = self.bandwidth_dict[best_ip]
                print(f"Best available bandwidth: {best_bandwidth} Mbps from {best_ip}")

                # Switch to the new stream if it's better than the current one
                if self.current_stream_ip != best_ip:
                    print(f"Switching to the stream from {best_ip}")
                    self.switch_stream(best_ip)

    def switch_stream(self, new_ip):
        """Stop the current stream and start a new one from the given IP."""
        # Stop the current stream receiver if it's running and notify the server to stop
        if self.current_stream_receiver is not None:
            self.send_stop_stream(self.current_stream_ip)  # Notify previous server to stop
            self.current_stream_receiver.stop_stream()
            self.current_stream_receiver = None

        # Initialize and start a new StreamReceiver before sending START_STREAM
        self.current_stream_ip = new_ip
        self.current_stream_receiver = StreamReceiver(new_ip, self.stream_port)

        # Start the StreamReceiver in a new thread to keep it non-blocking
        stream_thread = threading.Thread(target=self.current_stream_receiver.start_stream)
        stream_thread.start()

        # Send START_STREAM message to the new server
        self.send_start_stream(new_ip)

    def send_start_stream(self, server_ip):
        """Send a START_STREAM message to the specified server."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            message = b"START_STREAM"
            sock.sendto(message, (server_ip, self.port))
            print(f"Sent START_STREAM to {server_ip}:{self.port}")

    def send_stop_stream(self, server_ip):
        """Send a STOP_STREAM message to the specified server."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            message = b"STOP_STREAM"
            sock.sendto(message, (server_ip, self.port))
            print(f"Sent STOP_STREAM to {server_ip}:{self.port}")
