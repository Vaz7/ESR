from server import Server
import sys


video_path = "../videoB.mp4"


def main():
    if "--ip" not in sys.argv or len(sys.argv) != 3:
        print("Usage: python3 main.py --ip <BOOTSTRAPPER_IP_ADDRESS>")
        sys.exit(1)

    ip_index = sys.argv.index("--ip")
    ip_address = sys.argv[ip_index + 1]

    server = Server(video_path=video_path, bootstrapper_ip=ip_address, streaming_port=12346)  
    server.start()

if __name__ == "__main__":
    main()
