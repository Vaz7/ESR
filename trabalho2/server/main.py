from server import Server

def main():
    server = Server(port=12346)  
    server.start()

if __name__ == "__main__":
    main()
