import cv2
import socket
import struct
import threading
import time

class VideoStreamer:
    def __init__(self, video_path, port=12345, max_packet_size=60000):
        self.video_path = video_path
        self.port = port
        self.max_packet_size = max_packet_size
        self.clients = set()
        self.client_lock = threading.Lock()
        
        # Initialize the video capture
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Error opening video file: {video_path}")
        
        # Set up the UDP socket for streaming
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB buffer

    def add_client(self, client_addr):
        """Add a client to the list of active clients."""
        with self.client_lock:
            self.clients.add(client_addr)
            print(f"Client {client_addr} added.")

    def remove_client(self, client_addr):
        """Remove a client from the list of active clients."""
        with self.client_lock:
            if client_addr in self.clients:
                self.clients.remove(client_addr)
                print(f"Client {client_addr} removed.")

    def get_frame(self):
        """Retrieve and compress the next frame. Restart the video if it ends."""
        ret, frame = self.cap.read()
        if not ret:
            # Restart the video if it reaches the end
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()

        # Resize and compress frame
        frame = cv2.resize(frame, (640, 480))  # Resize to a fixed resolution
        _, img_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return img_encoded.tobytes()

    def broadcast_frame(self, frame_data):
        """Send the given frame to all active clients."""
        frame_size = len(frame_data)
        
        with self.client_lock:
            clients = list(self.clients)  # Make a copy of the client list

        for client_addr in clients:
            try:
                self.send_frame_to_client(frame_data, frame_size, client_addr)
            except Exception as e:
                print(f"Error sending frame to {client_addr}: {e}")
                self.remove_client(client_addr)  # Remove clients that encounter issues

    def send_frame_to_client(self, frame_data, frame_size, client_addr):
        """Send a frame to a specific client, splitting it into chunks if necessary."""
        packet_id = 0
        offset = 0

        while offset < frame_size:
            chunk = frame_data[offset:offset + self.max_packet_size - 8]
            chunk_size = len(chunk)
            offset += chunk_size

            # Pack packet_id and frame_size into the header
            packet_header = struct.pack('>HI', packet_id, frame_size)
            self.server_socket.sendto(packet_header + chunk, client_addr)

            packet_id += 1

    def start_streaming(self):
        """Start the loop that continuously streams the video frames."""
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        frame_delay = 1.0 / fps  # Calculate delay to match video FPS

        while True:
            frame_data = self.get_frame()  # Retrieve the current frame
            self.broadcast_frame(frame_data)  # Send it to all clients
            time.sleep(frame_delay)  # Delay to sync with video FPS
