from server import OverlayNode
import sys

def main():

    #A porta 12346 vai ser sempre a porta da stream
    server = OverlayNode(streaming_port=12346)
    server.start()

if __name__ == "__main__":
    main()
