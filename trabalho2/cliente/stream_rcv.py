import socket
import struct
import cv2
import numpy as np

class StreamReceiver:
    def __init__(self, port=12346, max_packet_size=60000):
        self.port = port
        self.max_packet_size = max_packet_size
        self.running = True
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Allow socket reuse
        self.client_socket.bind(('', self.port))
        self.target_ip = None  # Initialize target IP

    def set_target_ip(self, ip):
        """Set the target IP address for receiving data from the specified server."""
        self.target_ip = ip
        print(f"Set new target IP for stream: {self.target_ip}")

    def start_stream(self):
        """Start receiving video stream from the target IP."""
        print(f"Receiving stream on port {self.port}")
        data = b""
        expected_frame_size = None

        while self.running:
            try:
                # Receive a packet
                packet, addr = self.client_socket.recvfrom(self.max_packet_size)
                # Check if packet is from the correct target IP
                if self.target_ip and addr[0] != self.target_ip:
                    continue  # Ignore packets from other IPs
                
                packet_id, frame_size = struct.unpack('>HI', packet[:6])
                
                # Initialize frame buffer if this is a new frame
                if expected_frame_size is None or frame_size != expected_frame_size:
                    expected_frame_size = frame_size
                    data = b""

                data += packet[6:]
                
                # If we've collected the whole frame, decode and display it
                if len(data) >= expected_frame_size:
                    frame = np.frombuffer(data, dtype=np.uint8)
                    
                    try:
                        frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                        if frame is not None:
                            cv2.imshow("Video Stream", frame)
                            cv2.waitKey(1)
                    except cv2.error as e:
                        print("Frame decoding error:", e)
                    
                    data = b""  # Reset for next frame

            except socket.timeout:
                print("Stream receiver timeout. No data received.")
            except Exception as e:
                print("Error receiving stream:", e)

    def stop_stream(self):
        """Stop receiving video stream and reset the state."""
        self.running = False
        self.client_socket.close()
        cv2.destroyAllWindows()

