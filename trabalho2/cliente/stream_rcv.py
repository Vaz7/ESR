import socket
import struct
import cv2
import numpy as np

class StreamReceiver:
    def __init__(self, ip, port=12345, max_packet_size=60000):
        self.ip = ip
        self.port = port
        self.max_packet_size = max_packet_size
        self.running = False
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.settimeout(5)  # Set a timeout for receiving packets

    def start_stream(self):
        """Start receiving video stream from the server."""
        self.running = True
        print(f"Receiving stream from {self.ip}:{self.port}")
        data = b""
        expected_frame_size = None

        while self.running:
            try:
                # Receive a packet
                packet, _ = self.client_socket.recvfrom(self.max_packet_size)
                packet_id, frame_size = struct.unpack('>HI', packet[:6])
                
                # Initialize frame buffer if this is a new frame
                if expected_frame_size is None or frame_size != expected_frame_size:
                    expected_frame_size = frame_size
                    data = b""

                data += packet[6:]
                
                # If we've collected the whole frame, decode and display it
                if len(data) >= expected_frame_size:
                    frame = np.frombuffer(data, dtype=np.uint8)
                    frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                    if frame is not None:
                        cv2.imshow("Video Stream", frame)
                        cv2.waitKey(1)
                    data = b""  # Reset for next frame

            except socket.timeout:
                print("Stream receiver timeout. No data received.")

        self.client_socket.close()
        cv2.destroyAllWindows()

    def stop_stream(self):
        """Stop receiving video stream."""
        self.running = False
        print(f"Stopped receiving stream from {self.ip}:{self.port}")
