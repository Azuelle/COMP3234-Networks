from __future__ import annotations
import sys
import socket
import logging as log
import typing


def format_ip(addr: socket._RetAddress) -> str:
    return f"{addr[0]}:{addr[1]}"


def connect_server(addr: str, port: int) -> socket.socket:
    try:
        assert 0 <= port <= 65535
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((addr, port))
    except AssertionError as e:
        log.critical(f"Invalid port: {e}")
        exit(1)
    except socket.error as e:
        log.critical(f"Socket error: {e}")
        exit(1)
    log.info(f"Connection established to server at {addr}:{port}")
    log.info(f"This client is running at {format_ip(sock.getsockname())}")

    return sock


def send(sock: socket.socket, msg: str) -> None:
    try:
        sock.send(msg.encode("ascii"))
    except socket.error as e:
        log.critical(f"Socket error: {e}")
        exit(1)
    except UnicodeEncodeError as e:
        log.error(f"Failed to encode message: {e}")


def recv(sock: socket.socket) -> str:
    try:
        msg = sock.recv(1024).decode("ascii")
        assert msg
        log.info(f"Received {msg} from server")
    except socket.error as e:
        log.critical(f"Socket error: {e}")
        exit(1)
    except UnicodeDecodeError as e:
        log.error(f"Failed to decode message: {e}")
        return ""
    except AssertionError:
        log.critical(
            "Server disconnected unexpectedly: Received empty message (EOF)")
        exit(1)

    print(msg)
    return msg


def authenticate(sock: socket.socket) -> bool:
    authenticated = False
    while not authenticated:
        username = input("Please input your username: ")
        password = input("Please input your password: ")

        send(sock, f"/login {username} {password}")
        msg = recv(sock)

        if msg.split()[0] == "1001":
            authenticated = True

    return authenticated


def handle_exit(sock: socket.socket) -> None:
    sock.shutdown(1)
    while True:
        respond = recv(sock)
        if respond.split()[0] == "4001":
            sock.close()
            break


def handle_list(sock: socket.socket) -> None:
    recv(sock)


def handle_game(sock: socket.socket) -> None:
    while True:
        while True:
            guess = input("Guess true or false: ")
            if guess not in ["true", "false"]:
                print("Invalid guess. Please input 'true' or 'false'")
                continue
            else:
                break

        send(sock, f"/guess {guess}")
        respond = recv(sock)
        if respond.split()[0] in ["3021", "3022", "3023"]:
            break


def handle_enter(sock: socket.socket) -> None:
    respond = recv(sock)

    if respond.split()[0] == "3013":  # Room full
        return

    if respond.split()[0] == "3011":  # Wait
        while True:
            respond = recv(sock)
            if respond.split()[0] == "3012":  # Started
                break
    if respond.split()[0] == "3012":  # Started
        handle_game(sock)


COMMAND_HANDLERS = {"/exit": handle_exit,
                    "/list": handle_list, "/enter": handle_enter}
COMMAND_LENGTHS = {"/exit": 1, "/list": 1, "/enter": 2}


def handle_lobby(sock: socket.socket) -> None:
    exited = False
    while not exited:
        while True:
            msg = input("> ")
            if not msg:
                continue
            if msg.split()[0] not in COMMAND_HANDLERS:
                print(
                    "Invalid command. Available commands: /exit, /list, /enter <room number>")
                continue
            if len(msg.split()) != COMMAND_LENGTHS[msg.split()[0]]:
                print(f"Invalid number of arguments.")
                continue
            if msg:
                break

        send(sock, msg)
        COMMAND_HANDLERS[msg.split()[0]](sock)
        if msg == "/exit":
            exited = True


def main():
    # Verify arguments
    if len(sys.argv) > 4 or len(sys.argv) < 3:
        print("Usage: python GameClient.py <server address> <server port>")
        exit(1)

    if len(sys.argv) == 4:
        if sys.argv[3] == "--debug":
            log.basicConfig(level=log.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        else:
            print("Usage: python GameServer.py <port> <path/to/UserInfo.txt>")
            exit(1)
    else:
        log.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

    # Connect to server
    addr = sys.argv[1]
    port = int(sys.argv[2])
    sock = connect_server(addr, port)

    # USER AUTHENTICATION
    if not authenticate(sock):
        log.critical("Failed to authenticate user")
        exit(1)
    log.info("User successfully authenticated")

    # MAIN LOOP
    handle_lobby(sock)


if __name__ == "__main__":
    main()
