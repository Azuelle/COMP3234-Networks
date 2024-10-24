from pathlib import Path
import logging
import sys
import socket
import threading


class UserList:
    def __init__(path: Path, self) -> None:
        try:
            with open(path) as file:
                self.users = {line.strip().split(":")[0]: line.strip().split(":")[
                    1] for line in file.readlines()}
        except:
            logging.error(f"Failed to open user info file at {path}")
            exit(1)

    def validate(username: str, password: str, self) -> bool:
        return self.users.get(username) == password


def format_ip(addr: tuple[str, int]) -> str:
    return f"{addr[0]}:{addr[1]}"


if __name__ == "__main__":
    # Verify arguments
    if len(sys.argv) != 3:
        print("Usage: python GameServer.py <port> <path/to/UserInfo.txt>")
        exit(1)

    try:
        port = int(sys.argv[1])
        assert port > 0 and port < 65536
    except:
        logging.error("Invalid port number")
        exit(1)

    # Load user info
    try:
        user_info_path = Path(sys.argv[2])
        assert user_info_path.exists()
    except TypeError as e:
        logging.error(f"Invalid path: {e}")
        exit(1)
    except ValueError as e:
        logging.error(f"Invalid path: {e}")
        exit(1)
    except AssertionError:
        logging.error("File does not exist")
        exit(1)

    user_list = UserList(user_info_path)

    # Start server
    try:
        server_socket = socket.socket()
        server_socket.bind(("", port))
    except socket.error as e:
        logging.error(f"Socket error: {e}")
        exit(1)
    logging.info(f"Server started on port {port}")

    # Accept connections
    while True:
        try:
            conn, addr = server_socket.accept()
        except socket.error as e:
            logging.error(f"Socket error: {e}")
            exit(1)
        logging.info(f"{format_ip(addr)} established connection")
