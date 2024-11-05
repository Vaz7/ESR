from server import Server

video_path = "../videoB.mp4"

def main():
    server = Server(video_path=video_path, port=12346)  
    server.start()

if __name__ == "__main__":
    main()
