import sys
import socket
import time
import threading
import cv2
import numpy as np
import struct

MAX_UDP_PACKET_SIZE = 60000
BANDWIDTHINTERVAL= 10

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

def medeLarguraBanda(ip_list, port=12346, data_size=50000, repetitions=5):
    ipBW = {}
    for ip in ip_list:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            dummy_data = b'x' * data_size
            times = []

            for _ in range(repetitions):
                start_time = time.time()
                
                # Send data_size in the first 4 bytes, followed by the dummy_data
                client_socket.sendto(data_size.to_bytes(4, byteorder='big') + dummy_data, (ip, port))
                
                try:
                    # Wait for the echoed packet from the server
                    received_data, _ = client_socket.recvfrom(data_size + 4)
                    
                    # Check if the received data matches the sent data size
                    if len(received_data) == data_size:
                        end_time = time.time()
                        duration = end_time - start_time
                        times.append(duration)  # Store the duration for this round-trip
                    else:
                        print(f"Incomplete data from {ip}. Expected {data_size} bytes, got {len(received_data)} bytes.")
                
                except socket.timeout:
                    print(f"No response from {ip}, packet possibly lost.")
                    continue  # Skip to the next repetition if there's no response

            # Calculate the average bandwidth in Mbps if we have successful transmissions
            if times:
                avg_time = sum(times) / len(times)
                bandwidth_mbps = (data_size * 8) / (avg_time * 1_000_000)
                ipBW[ip] = round(bandwidth_mbps, 3)
                print(f"Average bandwidth for {ip}: {ipBW[ip]} Mbps")
            else:
                print(f"No successful transmissions for {ip}.")

        except Exception as e:
            print(f"Error during bandwidth calculation for {ip}: {e}")
        finally:
            client_socket.close()
    
    return ipBW

def receive_video_stream(client_socket, stop_event):
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
    try:
        fps_data, _ = client_socket.recvfrom(4)
        fps = int.from_bytes(fps_data, byteorder='big')
        frame_delay = 1.0 / fps if fps > 0 else 0.033  # Default to ~30 FPS if fps is zero to prevent division by zero
        print(f"Video frame rate: {fps} FPS")

        buffer = {}
        frame_size = None
        last_display_time = time.time()
        frame_buffer = []
        max_buffer_size = 100

        while not stop_event.is_set():
            packet, _ = client_socket.recvfrom(MAX_UDP_PACKET_SIZE)
            if len(packet) < 6:
                print("Received an invalid packet.")
                continue

            packet_id, total_size = struct.unpack('>HI', packet[:6])
            data = packet[6:]
            if frame_size is None:
                frame_size = total_size
            buffer[packet_id] = data
            received_size = sum(len(buffer[pid]) for pid in buffer)

            if received_size >= frame_size:
                frame_data = b''.join(buffer[pid] for pid in sorted(buffer))
                if len(frame_data) != frame_size:
                    buffer.clear()
                    frame_size = None
                    continue

                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is None:
                    print("Failed to decode frame.")
                    buffer.clear()
                    frame_size = None
                    continue

                frame_buffer.append(frame)
                if len(frame_buffer) > max_buffer_size:
                    frame_buffer.pop(0)

                if frame_buffer:
                    current_frame = frame_buffer.pop(0)
                    cv2.imshow('Stream', current_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

                current_time = time.time()
                time_elapsed = current_time - last_display_time
                if time_elapsed < frame_delay:
                    time.sleep(frame_delay - time_elapsed)
                last_display_time = time.time()

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
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.sendto(b'Start', (current_ip[0], 12345))
            stop_video_event = threading.Event()
            video_thread = threading.Thread(target=receive_video_stream, args=(client_socket, stop_video_event))
            video_thread.start()

            previous_ip = current_ip[0]
            while not stop_event.is_set() and current_ip[0] == previous_ip:
                time.sleep(1)

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
            best_bandwidth = ip_bandwidths[best_ip]
            print(f"Best bandwidth is {best_bandwidth} Mbps for IP: {best_ip}")
            if best_ip != current_ip[0]:
                print(f"Switching to better IP: {best_ip} ({best_bandwidth} Mbps)")
                current_ip[0] = best_ip
        else:
            print("Could not retrieve bandwidth info.")
        time.sleep(BANDWIDTHINTERVAL)

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
                current_ip = [best_ip]
                stop_event = threading.Event()
                video_thread = threading.Thread(target=manage_video_stream, args=(current_ip, stop_event))
                video_thread.start()
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
