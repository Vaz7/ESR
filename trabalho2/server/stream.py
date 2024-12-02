import cv2
import socket
import struct
import threading
import time

class VideoStreamer:
    def __init__(self, video_path, video_name, port=12346, max_packet_size=60000):
        self.video_path = video_path
        self.video_name = video_name  # Video name used as an identifier
        self.port = port
        self.max_packet_size = max_packet_size
        self.clients = set()
        self.client_lock = threading.Lock()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Initialize the video capture
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"Error opening video file: {video_path}")

        # Shared frame buffer to hold the latest frame
        self.current_frame = None
        self.frame_lock = threading.Lock()
        
        # Start the background frame reading thread
        self.streaming_thread = threading.Thread(target=self.read_frames)
        self.streaming_thread.daemon = True
        self.streaming_thread.start()

    def read_frames(self):
        """Continuously read frames from the video file, independent of client connections."""
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
        frame_delay = 1.0 / fps  # Calculate delay to match video FPS

        while True:
            ret, frame = self.cap.read()
            if not ret:
                # Restart the video if it reaches the end
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    print("Failed to read frame after resetting video. Stopping.")
                    break

            # Resize and compress the frame
            frame = cv2.resize(frame, (640, 480))
            _, img_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            frame_data = img_encoded.tobytes()

            # Store the frame in a shared buffer
            with self.frame_lock:
                self.current_frame = frame_data

            # Delay to sync with video FPS
            time.sleep(frame_delay)

    def add_client(self, client_addr):
        """Add a client to the list of active clients and start sending frames to them."""
        with self.client_lock:
            if client_addr not in self.clients:
                self.clients.add(client_addr)
                print(f"Client {client_addr} added for streaming.")
                threading.Thread(target=self.start_stream, args=(client_addr,), daemon=True).start()

    def remove_client(self, client_addr):
        """Remove a client from the list of active clients based on the IP address."""
        with self.client_lock:
            ip_to_remove = client_addr[0]  # Extract the IP part
            clients_to_remove = {client for client in self.clients if client[0] == ip_to_remove}  # Find matching clients

            if clients_to_remove:
                for client in clients_to_remove:
                    self.clients.remove(client)
                #print(f"Clients with IP {ip_to_remove} removed from streaming.")


    def start_stream(self, client_addr):
        """Send the latest frame to a specific client continuously."""
        while True:
            with self.client_lock:
                # Check if the IP of the client is still in the list
                active_ips = {client[0] for client in self.clients}  # Extract only the IPs
                
                if client_addr[0] not in active_ips:  # Compare the IP part
                    #print(f"Stopping stream to {client_addr} as they are no longer in the client list.")
                    break

            with self.frame_lock:
                frame_data = self.current_frame

            if frame_data:
                self.send_frame_to_client(frame_data, client_addr)

            time.sleep(1 / 30)  # Adjust this to match video FPS or client streaming needs


    def send_frame_to_client(self, frame_data, client_addr):
        """Send the frame to a specific client in chunks, targeting port 12346."""
        frame_size = len(frame_data)
        packet_id = 0
        offset = 0
    
        # Ensure video_name is a string and encode it
        if not isinstance(self.video_name, str):
            self.video_name = str(self.video_name)
    
        # Encode the video name as a fixed-size identifier (e.g., 16 bytes, padded with spaces if needed)
        video_id = self.video_name.encode('utf-8')[:16].ljust(16)
        # Override the port in client_addr with 12346
        target_addr = (client_addr[0], 12346)
    
        while offset < frame_size:
            chunk = frame_data[offset:offset + self.max_packet_size - 24]  # Adjust for 16-byte video ID and 8-byte header
            chunk_size = len(chunk)
            offset += chunk_size
    
            # Pack the video ID, packet ID, and frame size into the header
            packet_header = struct.pack('>16sHI', video_id, packet_id, frame_size)
            self.server_socket.sendto(packet_header + chunk, target_addr)
    
            packet_id += 1


    def stop_stream(self, client_addr):
        """Stop streaming to the specified client."""
        print(f"Stopping stream to {client_addr}")
        self.remove_client(client_addr)
