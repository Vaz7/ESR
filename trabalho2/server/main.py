from server import Server
import sys

def main():
    if "--ip" not in sys.argv or "--video" not in sys.argv or len(sys.argv) < 5:
        print("Usage: python3 main.py --ip <BOOTSTRAPPER_IP_ADDRESS> --video <video_path1> [<video_path2> ... <video_pathN>]")
        sys.exit(1)

    ip_index = sys.argv.index("--ip")
    video_index = sys.argv.index("--video")

    if ip_index + 1 >= len(sys.argv) or video_index + 1 >= len(sys.argv):
        print("Error: Missing IP address or video paths.")
        sys.exit(1)

    ip_address = sys.argv[ip_index + 1]
    video_paths = sys.argv[video_index + 1:]

    if not video_paths:
        print("Error: At least one video path must be provided.")
        sys.exit(1)

    # Initialize the server with the video paths and start it
    server = Server(video_paths=video_paths, bootstrapper_ip=ip_address, streaming_port=12346)
    server.start()

if __name__ == "__main__":
    main()
