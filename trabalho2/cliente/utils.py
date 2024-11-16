import socket
import time

def get_and_choose_video(ip, port, data_size=1024):
    """Send a latency request to retrieve available video names and prompt the user to choose one."""
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.settimeout(5)  # Set a timeout for packet responses

    try:
        # Send a single latency request
        client_socket.sendto("LATENCY_REQUEST".encode(), (ip, port))
        
        # Wait for a response within the timeout period
        received_data, _ = client_socket.recvfrom(data_size)
        if received_data.decode() == "NO_DATA":
            print(f"No video data available from {ip}.")
            return None
        else:
            parts = received_data.decode().split(",")
            if len(parts) < 3:
                print(f"Unexpected data format from {ip}: {received_data.decode()}")
                return None

            # Extract available video names from parts[2] onward
            available_videos = parts[2:]
            print("\nAvailable videos:")
            for idx, video in enumerate(available_videos):
                print(f"{idx + 1}: {video}")

            # Prompt the user to choose a video
            try:
                choice = int(input("\nEnter the number of the video you want to stream: "))
                if 1 <= choice <= len(available_videos):
                    chosen_video = available_videos[choice - 1]
                    print(f"Selected video: {chosen_video}")
                    return chosen_video
                else:
                    print("Invalid choice. Please try again.")
                    return None
            except ValueError:
                print("Invalid input. Please enter a number.")
                return None

    except socket.timeout:
        print(f"No response from {ip} within the timeout period.")
        return None
    except Exception as e:
        print(f"Error during video retrieval: {e}")
        return None
    finally:
        client_socket.close()
