import sys
import socket
import time
import threading
import cv2
import numpy as np

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
    data_size = 1024
    ipBW = {}

    for ip in ip_list:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((ip, port))

            dummy_data = b'x' * data_size
            start_time = time.time()

            client_socket.sendall(data_size.to_bytes(4, byteorder='big'))
            client_socket.sendall(dummy_data)

            received_data = b''
            while len(received_data) < data_size:
                packet = client_socket.recv(4096)
                if not packet:
                    break
                received_data += packet

            end_time = time.time()
            duration = end_time - start_time
            bandwidth_mbps = (data_size * 8) / (duration * 1_000_000)
            bandwidth_mbps = round(bandwidth_mbps, 3)
            ipBW[ip] = bandwidth_mbps

        except Exception as e:
            print(f"Error during bandwidth calculation for {ip}: {e}")
        finally:
            client_socket.close()

    return ipBW


def receive_video_stream(client_socket, stop_event):
    try:
        fps_data = client_socket.recv(4)
        if len(fps_data) < 4:
            print("Failed to receive frame rate.")
            return
        fps = int.from_bytes(fps_data, byteorder='big')
        frame_delay = 1.0 / fps  # Delay to match FPS

        print(f"Video frame rate: {fps} FPS")

        while not stop_event.is_set():
            frame_size_data = client_socket.recv(4)
            if len(frame_size_data) < 4:
                print("Connection closed or incomplete data received.")
                break

            frame_size = int.from_bytes(frame_size_data, byteorder='big')
            if frame_size == 0:
                print("End of video stream.")
                break

            img_bytes = b''
            while len(img_bytes) < frame_size:
                packet = client_socket.recv(frame_size - len(img_bytes))
                if not packet:
                    print("Failed to receive packet.")
                    break
                img_bytes += packet

            if len(img_bytes) != frame_size:
                print("Incomplete frame received, skipping.")
                continue

            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                print("Error: Failed to decode the frame.")
                continue

            cv2.imshow('Client Video Stream', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

            time.sleep(frame_delay)

    except Exception as e:
        print(f"Error receiving video stream: {e}")

    finally:
        cv2.destroyAllWindows()
        client_socket.close()


def manage_video_stream(current_ip, stop_event):
    video_thread = None

    while not stop_event.is_set():
        try:
            # Criar um socker para a conexao com o ip atual para receber a stream
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((current_ip[0], 12345))  # Use port 12345 for video stream

            # Arrancar a thread para receber a stream
            stop_video_event = threading.Event()  # Este event vai ser usado para matar a thread quando o ip mudar
            video_thread = threading.Thread(target=receive_video_stream, args=(client_socket, stop_video_event))
            video_thread.start()

            # testar para ver se o ip mudou
            previous_ip = current_ip[0]
            while not stop_event.is_set() and current_ip[0] == previous_ip:
                time.sleep(1)

            # Se o ip mudou mata se a thread e começa-se o processo novamente
            if current_ip[0] != previous_ip:
                print(f"IP changed to {current_ip[0]}, stopping current video thread.")
                stop_video_event.set()
                video_thread.join()

        except Exception as e:
            print(f"Error connecting to {current_ip[0]} for video stream: {e}")
            time.sleep(5) 

    # Ensure that the current video stream is stopped when the stop event is set
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