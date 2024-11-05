import socket
import struct
import threading


def handle_bandwidth_test(data, addr, bw_socket):
    try:
        # Step 1: Get the size of the data to expect from the first 4 bytes
        data_size = struct.unpack('!I', data[:4])[0]
        print(f"Expecting {data_size} bytes from {addr}")

        # Step 2: Initialize data receiving
        received_data = data[4:]  # Include any remaining bytes from initial data
        bytes_received = len(received_data)

        # Step 3: Continue receiving data in chunks until the full size is reached
        while bytes_received < data_size:
            chunk, _ = bw_socket.recvfrom(4096)
            if not chunk:
                print(f"Connection lost with {addr}")
                break
            received_data += chunk
            bytes_received += len(chunk)
        
        print(f"Received {bytes_received} bytes from {addr}")

        # Step 4: Send back the received data for bandwidth testing
        bw_socket.sendto(received_data, addr)

    except Exception as e:
        print(f"Error during bandwidth test with {addr}: {e}")

def serve_bandwidth_test():
    # Set up a UDP socket for bandwidth testing
    bw_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bw_socket.bind(('0.0.0.0', 12346))

    print("Bandwidth test server is listening on port 12346 (UDP)")

    while True:
        # Receive the initial data, which includes the 4-byte size indicator
        data, addr = bw_socket.recvfrom(4096)
        print(f"Received initial bandwidth test request from {addr}")

        # Handle each client request in a separate thread
        bw_handler = threading.Thread(target=handle_bandwidth_test, args=(data, addr, bw_socket))
        bw_handler.start()

def main():
    # Start the bandwidth testing server
    bandwidth_thread = threading.Thread(target=serve_bandwidth_test)
    bandwidth_thread.start()

if __name__ == "__main__":
    main()