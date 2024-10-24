import socket

def connect_to_server(ip, port=12222):
    try:
        # Create a socket object
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Connect to the server
        client_socket.connect((ip, port))

        print(f"Successfully connected to {ip} on port {port}")

        # Send a message to the server
        message = "Hello, Server!"
        client_socket.send(message.encode())

        # Wait for a response from the server
        response = client_socket.recv(1024)  # Buffer size of 1024 bytes
        print(f"Received response from server: {response.decode()}")

        # Close the connection
        client_socket.close()

    except Exception as e:
        print(f"Failed to connect to {ip} on port {port}. Error: {e}")

if __name__ == "__main__":
    ip_address = input("Enter the IP address to connect to: ")
    connect_to_server(ip_address)
