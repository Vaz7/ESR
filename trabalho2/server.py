import cv2
import socket
import threading
import time
import struct
import subprocess

VIDEO_PATH = "videoB.mp4"
MAX_UDP_PACKET_SIZE = 65507


def get_video_fps():
    try:
        # Use ffprobe to get only the FPS as a single output
        fps_output = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", 
             "stream=r_frame_rate", "-of", "csv=p=0", VIDEO_PATH],
            text=True
        ).strip()
        
        # Split if FPS is in fraction format
        if '/' in fps_output:
            num, denom = map(int, fps_output.split('/'))
            return num / denom
        else:
            return float(fps_output)

    except Exception as e:
        print(f"Error retrieving FPS with FFmpeg: {e}")
        return 30  # Default to 30 FPS if there’s an issue
    

def play_video_continuously(client_addrs, lock):
    fps = get_video_fps()
    frame_delay = 1.0 / fps

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 1MB send buffer

    cap = cv2.VideoCapture(VIDEO_PATH)
    if not cap.isOpened():
        print(f"Error opening video file {VIDEO_PATH}")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Restart the video if it ends
            continue

        # Resize and compress frame
        frame = cv2.resize(frame, (640, 480))
        _, img_encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        img_bytes = img_encoded.tobytes()
        frame_size = len(img_bytes)

        # Send frame to all clients
        with lock:
            for client_addr in list(client_addrs):
                try:
                    send_frame_to_client(server_socket, img_bytes, frame_size, client_addr)
                except Exception as e:
                    print(f"Error sending frame to {client_addr}: {e}")
                    client_addrs.remove(client_addr)

        time.sleep(frame_delay)




def send_frame_to_client(server_socket, frame_data, frame_size, client_addr):
    packet_id = 0
    offset = 0
    while offset < frame_size:
        chunk = frame_data[offset:offset + MAX_UDP_PACKET_SIZE - 8]
        chunk_size = len(chunk)
        offset += chunk_size

        packet_header = struct.pack('>HI', packet_id, frame_size)
        server_socket.sendto(packet_header + chunk, client_addr)

        packet_id += 1


def handle_client_udp(client_addr, client_addrs, lock):
    fps = get_video_fps()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.sendto(int(fps).to_bytes(4, byteorder='big'), client_addr)

    # Add the client to the active client list
    with lock:
        client_addrs.add(client_addr)
    print(f"Client {client_addr} added to active connections.")


def serve_video_stream_udp(client_addrs, lock):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('0.0.0.0', 12345))
    print("Video streaming server (UDP) is listening on port 12345...")

    while True:
        data, client_addr = server_socket.recvfrom(1024)
        print(f"Connection from {client_addr} has been established for video streaming.")
        
        # Handle the new client in a separate thread
        client_handler = threading.Thread(target=handle_client_udp, args=(client_addr, client_addrs, lock))
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
    client_addrs = set()  # A set to track active client addresses
    lock = threading.Lock()

    # Start the video playback thread
    video_thread = threading.Thread(target=play_video_continuously, args=(client_addrs, lock))
    video_thread.start()

    # Start the video streaming server to listen for new clients
    stream_thread = threading.Thread(target=serve_video_stream_udp, args=(client_addrs, lock))
    stream_thread.start()

    # Start the bandwidth testing server in another thread
    bandwidth_thread = threading.Thread(target=serve_bandwidth_test)
    bandwidth_thread.start()

    video_thread.join()
    stream_thread.join()
    bandwidth_thread.join()

if __name__ == "__main__":
    main()
