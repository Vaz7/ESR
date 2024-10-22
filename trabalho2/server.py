import cv2
import socket
import threading
import os
import time

# Specify the fixed video file path here
VIDEO_PATH = "videoA.mp4"

def handle_client(client_socket, addr):
    cap = cv2.VideoCapture(VIDEO_PATH)

    if not cap.isOpened():
        print(f"Error opening video file {VIDEO_PATH}")
        client_socket.sendall(b"ERROR: Unable to open video")
        client_socket.close()
        return

    # Send the frame rate of the video
    fps = cap.get(cv2.CAP_PROP_FPS)
    client_socket.sendall(int(fps).to_bytes(4, byteorder='big'))

    while True:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                # Restart the video loop
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            _, img_encoded = cv2.imencode('.jpg', frame)
            img_bytes = img_encoded.tobytes()

            # Send the frame size and the frame data
            client_socket.sendall(len(img_bytes).to_bytes(4, byteorder='big'))
            client_socket.sendall(img_bytes)

    cap.release()
    print(f"Video '{VIDEO_PATH}' has been streamed to {addr}")
    client_socket.sendall(b"END_STREAM")
    client_socket.close()


def serve_video_stream():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 12345))
    server_socket.listen(5)

    print("Video streaming server is listening on port 12345...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr} has been established for video streaming.")
        client_handler = threading.Thread(target=handle_client, args=(client_socket, addr))
        client_handler.start()

    server_socket.close()


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
    bw_socket.bind(('0.0.0.0', 12346))  # Use a different port for bandwidth test
    bw_socket.listen(5)

    print("Bandwidth test server is listening on port 12346...")

    while True:
        client_socket, addr = bw_socket.accept()
        print(f"Connection from {addr} has been established for bandwidth testing.")
        bw_handler = threading.Thread(target=handle_bandwidth_test, args=(client_socket, addr))
        bw_handler.start()

    bw_socket.close()


def main():
    # Start the video streaming server in a separate thread
    video_thread = threading.Thread(target=serve_video_stream)
    video_thread.start()

    # Start the bandwidth testing server in another thread
    bandwidth_thread = threading.Thread(target=serve_bandwidth_test)
    bandwidth_thread.start()

    video_thread.join()
    bandwidth_thread.join()


if __name__ == "__main__":
    main()
