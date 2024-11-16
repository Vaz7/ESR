import threading
import time
import socket
from latency import LatencyMonitor
from stream_rcv import StreamReceiver

class Client:
    def __init__(self, ip_list, port=13333, stream_port=12346):
        self.port = port
        self.stream_port = stream_port
        self.latency_dict = {}  # Shared dictionary for all IPs' latency measurements
        self.monitors = []  # List to keep track of monitor threads
        self.ip_list = ip_list
        self.current_stream_ip = None
        self.available_videos = []  # List of available videos
        self.lock = threading.Lock()

        # Initialize a single StreamReceiver to receive data on stream_port
        self.stream_receiver = StreamReceiver(self.stream_port)
        self.stream_thread = threading.Thread(target=self.stream_receiver.start_stream)
        self.stream_thread.start()  # Start the receiver thread once

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
            monitor = LatencyMonitor(ip, 13335, self.latency_dict)
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
            time.sleep(5)  # Wait 5 seconds to check latency updates
            
            with self.lock:
                # Find the IP with the lowest latency
                best_ip = min(self.latency_dict, key=self.latency_dict.get, default=None)
                if best_ip is None:
                    continue
                
                best_latency = self.latency_dict[best_ip]
                print(f"Best available latency: {best_latency} ms from {best_ip}")

                # If we have a new stream IP or no current stream, prompt user to choose a video
                if self.current_stream_ip != best_ip:
                    self.current_stream_ip = best_ip
                    self.receive_timestamp_and_videos(best_ip)
                    self.prompt_video_choice(best_ip)

    def receive_timestamp_and_videos(self, server_ip):
        """Receive a timestamp message containing the available video list from the server."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)  # Set a timeout for the connection
                sock.connect((server_ip, self.port))  # Connect to the server's control port
                
                response = sock.recv(4096).decode()
                if response:
                    # Assume the response format is "TIMESTAMP,video1,video2,video3"
                    parts = response.split(',', 1)  # Split only once to separate timestamp from video list
                    if len(parts) > 1:
                        self.available_videos = parts[1].split(',')  # Extract video list
                        print(f"Available videos from {server_ip}: {', '.join(self.available_videos)}")
                    else:
                        print(f"Received timestamp but no video list from {server_ip}.")
        except Exception as e:
            print(f"Failed to receive timestamp and video list from {server_ip}. Error: {e}")

    def prompt_video_choice(self, server_ip):
        """Prompt the user to choose a video and handle starting the stream."""
        if not self.available_videos:
            print("No available videos to display.")
            return

        print("\nChoose a video to stream:")
        for idx, video in enumerate(self.available_videos):
            print(f"{idx + 1}: {video}")

        try:
            choice = int(input("Enter the number of the video you want to stream: "))
            if 1 <= choice <= len(self.available_videos):
                selected_video = self.available_videos[choice - 1]
                print(f"Starting stream for video: {selected_video}")
                self.send_start_stream(server_ip, selected_video)
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    def send_start_stream(self, server_ip, video_name):
        """Send a START_STREAM message with the video name to the specified server via TCP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)  # Set a timeout for the connection
                sock.connect((server_ip, self.port))  # Connect to the server's control port
                message = f"START_STREAM {video_name}"
                sock.sendall(message.encode())
                print(f"Sent START_STREAM for {video_name} to {server_ip}:{self.port}")
        except Exception as e:
            print(f"Failed to send START_STREAM for {video_name} to {server_ip}. Error: {e}")

    def send_stop_stream(self, server_ip, video_name):
        """Send a STOP_STREAM message with the video name to the specified server via TCP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)  # Set a timeout for the connection
                sock.connect((server_ip, self.port))  # Connect to the server's control port
                message = f"STOP_STREAM {video_name}"
                sock.sendall(message.encode())
                print(f"Sent STOP_STREAM for {video_name} to {server_ip}:{self.port}")
        except Exception as e:
            print(f"Failed to send STOP_STREAM for {video_name} to {server_ip}. Error: {e}")
