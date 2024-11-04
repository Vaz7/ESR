import sys
import socket
import time
import threading
import cv2
import numpy as np
import struct

MAX_UDP_PACKET_SIZE = 65000

def validateIpAddress(ipAddr):
    parts = ipAddr.split(".")
    if len(parts) != 4:
        return False

    for part in parts:
        if not part.isdigit():
            return False
        num = int(part)
        if num < 0 or num > 255:
            return False

    return True


def medeLarguraBanda(ip_list):
    port = 12346
    data_size = 10000  # Ensure this is <= 65507 to fit within a single UDP packet
    ipBW = {}

    for ip in ip_list:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Prepare data to send as a single packet
            dummy_data = b'x' * data_size
            start_time = time.time()

            # Send the data size header and data to the server in one packet
            client_socket.sendto(data_size.to_bytes(4, byteorder='big') + dummy_data, (ip, port))

            # Receive a single response packet
            received_data, _ = client_socket.recvfrom(65507)

            # Calculate bandwidth if received data matches the sent size
            if len(received_data) == data_size:
                end_time = time.time()
                duration = end_time - start_time
                bandwidth_mbps = (data_size * 8) / (duration * 1_000_000)
                bandwidth_mbps = round(bandwidth_mbps, 3)
                ipBW[ip] = bandwidth_mbps
            else:
                print(f"Incomplete data received from {ip}. Expected {data_size} bytes, got {len(received_data)} bytes.")

        except Exception as e:
            print(f"Error during bandwidth calculation for {ip}: {e}")
        finally:
            client_socket.close()

    return ipBW



def receive_video_stream(client_socket, stop_event):
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 1MB receive buffer

    try:
        # Receive FPS from server and calculate frame delay
        fps_data, _ = client_socket.recvfrom(4)
        fps = int.from_bytes(fps_data, byteorder='big')
        frame_delay = 1.0 / fps

        print(f"Video frame rate: {fps} FPS")

        buffer = {}
        frame_size = None
        last_display_time = time.time()

        # Circular frame buffer to store up to 50 frames
        frame_buffer = []
        max_buffer_size = 100

        while not stop_event.is_set():
            packet, _ = client_socket.recvfrom(MAX_UDP_PACKET_SIZE)
            if len(packet) < 6:  # Expecting a 6-byte header
                print("Received an invalid packet.")
                continue

            # Unpack packet ID and frame size
            packet_id, total_size = struct.unpack('>HI', packet[:6])
            data = packet[6:]

            # Initialize frame size for new frame
            if frame_size is None:
                frame_size = total_size

            # Store packet data in buffer
            buffer[packet_id] = data

            # Check if the entire frame has been received
            received_size = sum(len(buffer[pid]) for pid in buffer)
            if received_size >= frame_size:
                # Assemble the complete frame from buffer
                frame_data = b''.join(buffer[pid] for pid in sorted(buffer))
                if len(frame_data) != frame_size:
                    buffer.clear()
                    frame_size = None
                    continue

                # Decode the frame data
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is None:
                    print("Failed to decode frame.")
                    buffer.clear()
                    frame_size = None
                    continue

                # Add frame to the circular buffer
                frame_buffer.append(frame)
                if len(frame_buffer) > max_buffer_size:
                    frame_buffer.pop(0)  # Remove the oldest frame

                # Display the latest frame in the buffer
                if frame_buffer:
                    current_frame = frame_buffer.pop(0)
                    cv2.imshow('Os Javalis Stream', current_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                # Track the timing for smoother playback
                current_time = time.time()
                time_elapsed = current_time - last_display_time
                if time_elapsed < frame_delay:
                    time.sleep(frame_delay - time_elapsed)
                last_display_time = time.time()

                # Reset for the next frame
                buffer.clear()
                frame_size = None

    except Exception as e:
        print(f"Error receiving video stream: {e}")
    finally:
        cv2.destroyAllWindows()
        client_socket.close()


def manage_video_stream(current_ip, stop_event):
    video_thread = None

    while not stop_event.is_set():
        try:
            # Create UDP socket to connect to the current IP for the stream
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(b'Start', (current_ip[0], 12345))  # Initial message to start the stream

            # Start thread to receive the video stream
            stop_video_event = threading.Event()
            video_thread = threading.Thread(target=receive_video_stream, args=(client_socket, stop_video_event))
            video_thread.start()

            # Monitor for IP changes
            previous_ip = current_ip[0]
            while not stop_event.is_set() and current_ip[0] == previous_ip:
                time.sleep(1)

            # Stop video thread if IP has changed
            if current_ip[0] != previous_ip:
                print(f"IP changed to {current_ip[0]}, stopping current video thread.")
                stop_video_event.set()
                video_thread.join()
        except Exception as e:
            print(f"Error connecting to {current_ip[0]} for video stream: {e}")
            time.sleep(5)
    if video_thread:
        stop_video_event.set()
        video_thread.join()


def monitor_bandwidth(ip_list, current_ip, stop_event):

    while not stop_event.is_set():
        print("Checking bandwidth...")

        ip_bandwidths = medeLarguraBanda(ip_list)

        if ip_bandwidths:
            best_ip = max(ip_bandwidths, key=ip_bandwidths.get)
            if best_ip != current_ip[0]:
                print(f"Switching to better IP: {best_ip} ({ip_bandwidths[best_ip]} Mbps)")
                current_ip[0] = best_ip
        else:
            print("Could not retrieve bandwidth info.")

        time.sleep(60)


def main():
    args = sys.argv[1:]
    ip_list = []

    if "--ip" in args:
        ip_index = args.index("--ip") + 1

        while ip_index < len(args) and not args[ip_index].startswith("--"):
            if validateIpAddress(args[ip_index]):
                ip_list.append(args[ip_index])
                ip_index += 1
            else:
                print(f"Invalid IP address: {args[ip_index]}")
                sys.exit(1)

        if ip_list:
            ip_bandwidths = medeLarguraBanda(ip_list)

            if ip_bandwidths:
                best_ip = max(ip_bandwidths, key=ip_bandwidths.get)
                print(f"Starting stream from: {best_ip} ({ip_bandwidths[best_ip]} Mbps)")

                current_ip = [best_ip]  # Lista para poder ser alterado nas threads
                stop_event = threading.Event()

                # Arrancar a thread que gere a stream
                video_thread = threading.Thread(target=manage_video_stream, args=(current_ip, stop_event))
                video_thread.start()

                # Arrancar a thread que mede a mediçao da largura de banda
                monitor_thread = threading.Thread(target=monitor_bandwidth, args=(ip_list, current_ip, stop_event))
                monitor_thread.start()

                try:
                    video_thread.join()
                    monitor_thread.join()
                except KeyboardInterrupt:
                    print("Stopping threads...")
                    stop_event.set()
                    video_thread.join()
                    monitor_thread.join()
            else:
                print("Could not retrieve bandwidth info for the IPs provided.")
        else:
            print("No IP addresses provided after --ip.")
    else:
        print("No --ip flag provided.")


if __name__ == "__main__":
    main()