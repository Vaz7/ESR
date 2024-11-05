import threading
from bandwidth import BandwidthMonitor


class Client:
    def __init__(self, ip_list, port=12346):
        self.port = port
        self.bandwidth_dict = {}  # Shared dictionary for all IPs' bandwidth measurements
        self.monitors = []  # List to keep track of monitor threads
        self.ip_list = ip_list

    
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
            raise ValueError(f"Invalid IP address: {ip}")

        for ip in self.ip_list:
            monitor = BandwidthMonitor(ip, self.port, self.bandwidth_dict)
            self.monitors.append(monitor)

        # Start a thread for each BandwidthMonitor instance
        for monitor in self.monitors:
            monitor_thread = threading.Thread(target=monitor.measure_bandwidth)
            monitor_thread.start()