import sys
import json
import socket
import threading

def readJsonFile(filePath):
    print("Reading file: " + filePath)
    with open(filePath, 'r') as file:
        return json.load(file)

def handle_client(client_socket, addr, vizinhancas):
    client_ip = addr[0]
    
    if client_ip in vizinhancas:
        neighbors = vizinhancas[client_ip]
        response = ', '.join(neighbors)
        client_socket.send(response.encode())
    else:
        response = "ERROR"
        client_socket.send(response.encode())
    
    client_socket.close()

def serve_vizinhos(vizinhacas):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 12222))
    server_socket.listen(10)

    print("Bootstrapper server is listening on port 12222...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr} has been established for retrieving neighbour info.")
        client_handler = threading.Thread(target=handle_client, args=(client_socket, addr, vizinhacas))
        client_handler.start()

def main():
    args = sys.argv[1:]

    if "--file" not in args:
        print("Usage: python3 bootstrapper.py --file <JSON_FILE_PATH>")
        sys.exit(1)
    
    file_index = args.index("--file") + 1

    # Check if the file path is provided and valid
    if file_index >= len(args) or args[file_index].startswith("--"):
        print("Usage: python3 bootstrapper.py --file <JSON_FILE_PATH>")
        sys.exit(1)

    file_path = args[file_index]
    vizinhancas = readJsonFile(file_path)

    requestsThread = threading.Thread(target=serve_vizinhos, args=(vizinhancas,))
    requestsThread.start()
    requestsThread.join()

if __name__ == "__main__":
    main()
