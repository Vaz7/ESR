import cv2
import socket
import numpy as np
import time

def receive_stream(client_socket):
    print("Streaming video...")

    # Receive and parse the frame rate sent by the server
    fps_data = client_socket.recv(4)
    if len(fps_data) < 4:
        print("Failed to receive frame rate.")
        return
    fps = int.from_bytes(fps_data, byteorder='big')
    frame_delay = 1.0 / fps  # Calculate the delay between frames in seconds

    print(f"Video frame rate: {fps} FPS")

    while True:
        try:
            # Receive the size of the incoming frame (4 bytes)
            frame_size_data = client_socket.recv(4)
            if len(frame_size_data) < 4:
                print("Connection closed or incomplete data received.")
                break

            frame_size = int.from_bytes(frame_size_data, byteorder='big')
            if frame_size == 0:
                print("End of video stream.")
                break

            # Accumulate the image bytes until the full frame is received
            img_bytes = b''
            while len(img_bytes) < frame_size:
                packet = client_socket.recv(frame_size - len(img_bytes))
                if not packet:
                    print("Failed to receive packet.")
                    break
                img_bytes += packet

            # If the frame is incomplete, skip decoding
            if len(img_bytes) != frame_size:
                print("Incomplete frame received, skipping.")
                continue

            # Decode and display the frame
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Check if the frame was successfully decoded
            if frame is None:
                print("Error: Failed to decode the frame.")
                continue

            # Display the frame in a window
            cv2.imshow('Client Video Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            # Wait for the appropriate time to match the frame rate
            time.sleep(frame_delay)

        except ConnectionAbortedError:
            print("Connection closed by server.")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            break

    cv2.destroyAllWindows()
    client_socket.close()

if __name__ == "__main__":
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(('127.0.0.1', 12345))

    receive_stream(client_socket)
