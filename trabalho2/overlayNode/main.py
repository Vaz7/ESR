from server import Server
import sys

def main():
    if "--ip" not in sys.argv or len(sys.argv) != 3:
        print("Usage: python3 main.py --ip <BOOTSTRAPPER_IP_ADDRESS>")
        sys.exit(1)


    ip_index = sys.argv.index("--ip")
    ip_address = sys.argv[ip_index + 1]

    #A porta 12346 vai ser sempre a porta da stream
    server = Server(12346,ip_address)
    server.start()

if __name__ == "__main__":
    main()
