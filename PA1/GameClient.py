import sys
import socket
import logging as log


def connect_server(addr: str, port: int) -> socket.socket:
    try:
        assert 0 <= port <= 65535
        sock = socket.socket()
        sock.connect((addr, port))
    except AssertionError as e:
        log.error(f"Invalid port: {e}")
        exit(1)
    except socket.error as e:
        print(f"Socket error: {e}")
        exit(1)
    log.info("Connection established to server at {addr}:{port}")

    return sock


def authenticate(sock: socket.socket) -> bool:
    authenticated = False
    while not authenticated:
        username = input("Please input your username: ")
        password = input("Please input your password: ")

        try:
            sock.send(f"/login {username} {password}".encode("ascii"))
            msg = sock.recv(1024).decode("ascii")
        except socket.error as e:
            log.error(f"Socket error: {e}")
            exit(1)

        if msg.split()[0] == "1001":
            authenticated = True
            print("Login successful.")
        else:
            print("Login failed. Please try again.")

    return authenticated


if __name__ == "__main__":
    # Verify arguments
    if len(sys.argv) != 3:
        print("Usage: python GameClient.py <server address> <server port>")
        exit(1)

    # Connect to server
    addr = sys.argv[1]
    port = int(sys.argv[2])
    sock = connect_server(addr, port)

    # USER AUTHENTICATION
    if not authenticate(sock):
        log.error("Failed to authenticate user")
        exit(1)

    # MAIN LOOP
    while True:
        pass
