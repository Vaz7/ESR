from client import Client
import sys


def main():
    args = sys.argv[1:]  # Ip's dos servidores
    ip_list = []

    # this main should place all ip addresses in the ip_list and start the client
    # it should also handle the case where no ip addresses are provided
    # and print an error message in that case
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
        client.start_monitoring()
        


if __name__ == "__main__":
    main()