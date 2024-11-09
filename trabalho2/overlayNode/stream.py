import socket
import threading
import time


class StreamManager:
    def __init__(self, latency_manager, vizinhos):
        self.latency_manager = latency_manager
        self.vizinhos = vizinhos
        self.current_stream_target = None
        self.lock = threading.Lock()

    
    def check_and_update_stream_path(self):
        """Continuously check for the best path and handle stream start/stop as needed."""
        while True:
            best_node = self.latency_manager.get_best_server()

            with self.lock:
                if best_node and best_node != self.current_stream_target:
                    # Handle stopping the current stream
                    if self.current_stream_target:
                        self.send_message(self.current_stream_target, "STOP_STREAM")
                        print(f"Sent STOP_STREAM to {self.current_stream_target}")

                    # Handle starting the new stream
                    self.current_stream_target = best_node
                    self.send_message(self.current_stream_target, "START_STREAM")
                    print(f"Sent START_STREAM to {self.current_stream_target}")

            time.sleep(5)

    def send_message(self, ip, message):
        """Send a control message to the specified IP using TCP."""
        if ip not in self.vizinhos:
            print(f"IP {ip} is not a known neighbor. Skipping message.")
            return

        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.settimeout(5)
            client_socket.connect((ip, 13333))  # Control port
            client_socket.send(message.encode())
            client_socket.close()
        except Exception as e:
            print(f"Failed to send {message} to {ip}. Error: {e}")

    def get_current_stream_target(self):
        """Return the current target for streaming."""
        with self.lock:
            return self.current_stream_target


        