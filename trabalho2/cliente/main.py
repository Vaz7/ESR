import sys
from client import Client

def main():
    args = sys.argv[1:]  # IPs of the servers
    ip_list = []

    if "--ip" in args:
        ip_index = args.index("--ip") + 1
        while ip_index < len(args) and not args[ip_index].startswith("--"):
            ip_list.append(args[ip_index])
            ip_index += 1
    else:
        print("No --ip flag provided.")
        sys.exit(1)

    if ip_list:
        # Start the client
        client = Client(ip_list)
    else:
        print("No IP addresses provided.")
        sys.exit(1)

if __name__ == "__main__":
    main()
