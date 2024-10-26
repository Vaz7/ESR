import cv2
import socket
import threading
import time
import queue
import struct

# Specify the fixed video file path here
VIDEO_PATH = "movie.Mjpeg"
MAX_UDP_PACKET_SIZE = 65507  # Maximum safe UDP packet size

# Shared queue to store the encoded frames
frame_queue = queue.Queue(maxsize=10)

def get_video_fps():
    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"Error: Unable to open video file {VIDEO_PATH}")
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return fps

def play_video_continuously():
    while True:
        cap = cv2.VideoCapture(VIDEO_PATH)  # Reinitialize at the start of each loop
        if not cap.isOpened():
            print(f"Error opening video file {VIDEO_PATH}")
            return

        fps = get_video_fps()
        frame_delay = 1.0 / fps
        while True:
            ret, frame = cap.read()
            if not ret:
                break  

            _, img_encoded = cv2.imencode('.jpg', frame)
            img_bytes = img_encoded.tobytes()

            # Put the encoded frame in the queue, blocking until there's space
            while True:
                try:
                    frame_queue.put(img_bytes, timeout=1)
                    break
                except queue.Full:
                    time.sleep(0.01)  # Queue is full, wait briefly

            time.sleep(frame_delay)

        cap.release()


def handle_client_udp(server_socket, client_addr):
    fps = get_video_fps()
    server_socket.sendto(int(fps).to_bytes(4, byteorder='big'), client_addr)

    while True:
        try:
            frame_data = frame_queue.get(timeout=1)
            frame_size = len(frame_data)

            # Fragment frame into packets if it exceeds MAX_UDP_PACKET_SIZE
            packet_id = 0
            offset = 0
            while offset < frame_size:
                chunk = frame_data[offset:offset + MAX_UDP_PACKET_SIZE - 8]
                chunk_size = len(chunk)
                offset += chunk_size

                # Packet structure: [Packet ID, Total Packets, Frame Chunk]
                packet_header = struct.pack('>HI', packet_id, frame_size)
                server_socket.sendto(packet_header + chunk, client_addr)

                packet_id += 1
        except queue.Empty:
            print(f"No frames to send to {client_addr}.")
            break
        except (ConnectionResetError, BrokenPipeError, OSError):
            print(f"Connection lost to {client_addr}.")
            break

def serve_video_stream_udp():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('0.0.0.0', 12345))
    print("Video streaming server (UDP) is listening on port 12345...")

    while True:
        # Wait for the initial connection message from client
        data, client_addr = server_socket.recvfrom(1024)
        print(f"Connection from {client_addr} has been established for video streaming.")
        client_handler = threading.Thread(target=handle_client_udp, args=(server_socket, client_addr))
        client_handler.start()

def handle_bandwidth_test(client_socket, addr):
    try:
        while True:
            data_size = client_socket.recv(4)
            if len(data_size) < 4:
                break

            data_size = int.from_bytes(data_size, byteorder='big')

            # Receive the actual data sent by the client
            data = client_socket.recv(data_size)
            if len(data) < data_size:
                print("Incomplete data received.")
                break

            # Send the same amount of data back to the client
            client_socket.sendall(len(data).to_bytes(4, byteorder='big'))
            client_socket.sendall(data)

    except Exception as e:
        print(f"Error during bandwidth test: {e}")
    finally:
        client_socket.close()

def serve_bandwidth_test():
    bw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bw_socket.bind(('0.0.0.0', 12346))
    bw_socket.listen(5)

    print("Bandwidth test server is listening on port 12346...")

    while True:
        client_socket, addr = bw_socket.accept()
        print(f"Connection from {addr} has been established for bandwidth testing.")
        bw_handler = threading.Thread(target=handle_bandwidth_test, args=(client_socket, addr))
        bw_handler.start()

    bw_socket.close()

def main():
    # Start the video playback thread
    video_thread = threading.Thread(target=play_video_continuously)
    video_thread.start()

    # Start the video streaming server in a separate thread
    stream_thread = threading.Thread(target=serve_video_stream_udp)
    stream_thread.start()

    # Start the bandwidth testing server in another thread
    bandwidth_thread = threading.Thread(target=serve_bandwidth_test)
    bandwidth_thread.start()

    video_thread.join()
    stream_thread.join()
    bandwidth_thread.join()

if __name__ == "__main__":
    main()
