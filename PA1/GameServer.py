from __future__ import annotations
from pathlib import Path
import logging as log
import sys
import socket
import threading
from enum import Enum, auto
from typing import cast
import random


def format_ip(addr: socket._RetAddress) -> str:
    return f"{addr[0]}:{addr[1]}"


class UserList:
    def __init__(self, path: Path | None = None) -> None:
        self.users = dict[str, str]()
        if Path is not None:
            self.load(cast(Path, path))

    def load(self, path: Path) -> None:
        try:
            with open(path) as file:
                self.users = {line.strip().split(":")[0]: line.strip().split(":")[
                    1] for line in file.readlines()}
        except:
            log.error(f"Failed to open user info file at {path}")

    def validate(self, username: str, password: str) -> bool:
        return self.users.get(username) == password


class GameRoom:
    def __init__(self) -> None:
        self.players = list[Player]()
        self.lock = threading.Lock()

    def __len__(self) -> int:
        return len(self.players)

    def add_player(self, player: Player) -> None:
        with self.lock:
            self.players.append(player)

    def remove_player(self, player: Player) -> None:
        with self.lock:
            self.players.remove(player)

    def start(self) -> None:
        raise NotImplementedError


class GuessGameRoom(GameRoom):
    def __init__(self) -> None:
        super().__init__()
        self.MAX_PLAYERS = 2

    def add_player(self, player: Player) -> None:
        with self.lock:
            if len(self.players) == self.MAX_PLAYERS:
                player.send("3013 The room is full")
                return

            self.players.append(player)
            with player.lock:
                player.join(self)

            if len(self.players) == self.MAX_PLAYERS:
                self.start()
            else:
                player.send("3011 Wait")

    def get_guess(self, player: Player) -> None:
        log.info(f"Waiting for guess from {player}")
        while True:
            try:
                with player.lock:
                    msg = player.sock.recv(1024).decode("ascii").split()
                    if len(msg) == 2 and msg[0] == "/guess" and msg[1] in ["true", "false"]:
                        self.guesses[player] = msg[1] == "true"
                        return
                log.error(f"Received invalid message")
                player.send(
                    "4002 Unrecognized message")
            except UnicodeDecodeError as e:
                log.error(f"Unicode decode error: {e}")
                player.send(
                    "4002 Unrecognized message")

    def start(self) -> None:
        try:
            assert len(self.players) == self.MAX_PLAYERS
        except AssertionError:
            log.error("Invalid number of players")
            return

        try:
            # Brodcast game start
            log.info("Starting game in room with players: ", self.players)
            self.guesses: dict[Player, bool | None] = {
                player: None for player in self.players}

            threads = []
            for player in self.players:
                log.info(f"Notifying {player}")
                with player.lock:
                    player.state = Player.State.INGAME
                    player.send(
                        "3012 Game started. Please guess true or false")

                t = threading.Thread(target=self.get_guess, args=(player,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Game main logic
            if self.guesses[self.players[0]] == self.guesses[self.players[1]]:
                # Tie
                for player in self.players:
                    with player.lock:
                        player.send("3023 The result is a tie")
            else:
                ans = random.choice([True, False])
                winner_id = self.guesses[self.players[1]] == ans

                winner = self.players[winner_id]
                with winner.lock:
                    winner.send("3021 You won this game")

                loser = self.players[not winner_id]
                with loser.lock:
                    loser.send("3022 You lost this game")

        except Player.ExitedException as e:
            log.error(f"{e}")
            self.remove_player(e.player)

            # Resolve other players
            for player in self.players:
                if player == e.player:
                    continue

                if player.state != Player.State.INGAME:
                    continue

                try:
                    with player.lock:
                        player.send("3023 The result is a tie")
                except Player.ExitedException as e:
                    log.error(f"{e}")
                    self.remove_player(e.player)

            for player in self.players:
                player.leave()


ROOM_COUNT = 8
rooms = [GuessGameRoom() for _ in range(ROOM_COUNT)]


class Player:
    class ExitedException(Exception):
        def __init__(self, player: Player, *args, **kwargs) -> None:
            self.player = player
            super().__init__(*args)

    class State(Enum):
        LOBBY = auto()
        WAITING = auto()
        INGAME = auto()
        DISCONNECTED = auto()

    def __str__(self) -> str:
        return f"Player at {format_ip(self.sock.getsockname)}"

    def __init__(self, sock: socket.socket) -> None:
        self.state = Player.State.LOBBY
        self.room: GameRoom | None = None
        self.sock = sock
        self.lock = threading.Lock()
        self.exitedException = self.ExitedException(
            self, f"Player at {format_ip(sock.getsockname)} exited unexpectedly")

    def join(self, room: GameRoom) -> None:
        room.add_player(self)
        self.room = room
        self.state = Player.State.WAITING

    def leave(self) -> None:
        self.state = Player.State.LOBBY
        if self.room is not None:
            self.room.remove_player(self)
        self.room = None

    def exit(self) -> None:
        self.state = Player.State.DISCONNECTED

    def send(self, msg: str | bytes) -> None:
        try:
            if msg is str:
                self.sock.send(msg.encode("ascii"))
            elif msg is bytes:
                self.sock.send(cast(bytes, msg))
        except socket.error as e:
            log.error(f"Socket error: {e}")
            self.state = Player.State.DISCONNECTED
            raise self.exitedException


def authenticate(sock: socket.socket, user_list: UserList) -> bool:
    log.info(f"Authenticating {format_ip(sock.getsockname())}")
    authenticated = False
    while not authenticated:
        msg = sock.recv(1024).decode("ascii").split()
        if len(msg) == 3 and msg[0] == "/login":
            username, password = msg[1], msg[2]
            if user_list.validate(username, password):
                sock.send("1001 Authentication successful".encode("ascii"))
                authenticated = True
            else:
                sock.send("1002 Authentication failed".encode("ascii"))
        else:
            sock.send("4002 Unrecognized message".encode("ascii"))

    return authenticated


def handle_list(player: Player) -> None:
    player.send(
        f"3001 {len(rooms)} {' '.join([str(len(room)) for room in rooms])}"
    )


def handle_enter(player: Player, room_id: int) -> None:
    rooms[room_id].add_player(player)


def handle_unknown(player: Player) -> None:
    player.send("4002 Unrecognized message")


MSG_HANDLERS = {"/list": handle_list, "/enter": handle_enter}
MSG_LENGTHS = {"/list": 1, "/enter": 2}


def handle_client(sock: socket.socket, user_list: UserList) -> None:
    try:
        if not authenticate(sock, user_list):
            log.error("Failed to authenticate user")
            return
    except socket.error as e:
        log.error(f"Socket error: {e}")

    player = Player(sock)
    log.info(f"Player {player} successfully logged in")

    # Receive messages
    while True:
        try:
            msg = sock.recv(1024).decode("ascii").split()

            if msg[0] == "/exit" and len(msg) == 1:
                player.send("4001 Bye Bye")
                break
            elif msg[0] in MSG_HANDLERS and len(msg) == MSG_LENGTHS[msg[0]]:
                MSG_HANDLERS[msg[0]](player, *msg[1:])
            else:
                handle_unknown(player)

        except Player.ExitedException as e:
            log.error(f"{e}")
            break


def main() -> None:
    # Verify arguments
    if len(sys.argv) != 3:
        print("Usage: python GameServer.py <port> <path/to/UserInfo.txt>")
        exit(1)

    # Load user info
    try:
        user_info_path = Path(sys.argv[2])
        assert user_info_path.exists()
    except TypeError as e:
        log.error(f"Invalid path: {e}")
        exit(1)
    except ValueError as e:
        log.error(f"Invalid path: {e}")
        exit(1)
    except AssertionError:
        log.error("File does not exist")
        exit(1)

    user_list = UserList(user_info_path)

    # Start server
    try:
        port = int(sys.argv[1])
        assert 0 <= port <= 65535

        server_socket = socket.socket()
        server_socket.bind(("", port))
    except AssertionError as e:
        log.error(f"Invalid port: {e}")
        exit(1)
    except socket.error as e:
        log.error(f"Socket error: {e}")
        exit(1)
    log.info(f"Server started on port {port}")

    # Accept connections
    while True:
        try:
            conn, addr = server_socket.accept()
        except socket.error as e:
            log.error(f"Socket error when accepting client: {e}")
            continue

        log.info(f"Client {format_ip(addr)} established connection")
        threading.Thread(target=handle_client, args=(conn, user_list)).start()


if __name__ == "__main__":
    main()
