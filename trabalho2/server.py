import cv2
import socket
import threading
import time
import struct
import subprocess

VIDEO_PATH = "videoB.mp4"
MAX_UDP_PACKET_SIZE = 60000

#ha umas funcoes do cv2 que fazem isto, mas nao funcionam para todos os formatos
def get_video_fps():
    try:
        
        fps_output = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", 
             "stream=r_frame_rate", "-of", "csv=p=0", VIDEO_PATH],
            text=True
        ).strip()
        
        if '/' in fps_output:
            num, denom = map(int, fps_output.split('/'))
            return num / denom
        else:
            return float(fps_output)

    except Exception as e:
        print(f"Error retrieving FPS with FFmpeg: {e}")
        return 30  # Default to 30 FPS if there’s an issue
    

def play_video_continuously(client_addrs, client_lock):
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

        # Copy current clients to avoid holding lock
        with client_lock:
            current_clients = list(client_addrs)

        # Send frame to all clients
        for client_addr in current_clients:
            try:
                send_frame_to_client(server_socket, img_bytes, frame_size, client_addr)
            except Exception as e:
                print(f"Error sending frame to {client_addr}: {e}")
                # Remove clients that failed to receive frames
                with client_lock:
                    if client_addr in client_addrs:
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


def handle_client_udp(client_addr, client_addrs, client_lock):
    fps = get_video_fps()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        server_socket.sendto(int(fps).to_bytes(4, byteorder='big'), client_addr)

    # Add the client to the active client list
    with client_lock:
        client_addrs.add(client_addr)
    print(f"Client {client_addr} added to active connections.")


def serve_video_stream_udp(client_addrs, client_lock):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind(('0.0.0.0', 12345))
    print("Video streaming server (UDP) is listening on port 12345...")

    while True:
        data, client_addr = server_socket.recvfrom(1024)
        print(f"Connection from {client_addr} has been established for video streaming.")
        
        # Handle the new client in a separate thread
        client_handler = threading.Thread(target=handle_client_udp, args=(client_addr, client_addrs, client_lock))
        client_handler.start()


def handle_bandwidth_test(bw_socket, data, client_addr):
    try:
        # The first 4 bytes represent the data size
        data_size = int.from_bytes(data[:4], byteorder='big')
        received_data = data[4:]
        
        while len(received_data) < data_size:
            
            packet, _ = bw_socket.recvfrom(4096)
            received_data += packet

        bw_socket.sendto(received_data, client_addr)

    except Exception as e:
        print(f"Error during bandwidth test with {client_addr}: {e}")

def serve_bandwidth_test():
    bw_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bw_socket.bind(('0.0.0.0', 12346))
    print("Bandwidth test server is listening on port 12346")

    while True:
        #Aqui perguntam-se porque nao podia receber menos no buffer, eu tambem me perguntei isso
        #Acontece que quando se le 4096 da bosta do socker ele deita o resto dos dados fora e isto rebenta tudo lol
        data, client_addr = bw_socket.recvfrom(65507)
        print(f"Received bandwidth test request from {client_addr}")

        bw_handler = threading.Thread(target=handle_bandwidth_test, args=(bw_socket, data, client_addr))
        bw_handler.start()



def main():
    client_addrs = set()  # A set to track active client addresses
    client_lock = threading.Lock()

    # Start the video playback thread
    video_thread = threading.Thread(target=play_video_continuously, args=(client_addrs, client_lock))
    video_thread.start()

    # Start the video streaming server to listen for new clients
    stream_thread = threading.Thread(target=serve_video_stream_udp, args=(client_addrs, client_lock))
    stream_thread.start()

    # Start the bandwidth testing server in another thread
    bandwidth_thread = threading.Thread(target=serve_bandwidth_test)
    bandwidth_thread.start()

    video_thread.join()
    stream_thread.join()
    bandwidth_thread.join()

if __name__ == "__main__":
    main()
