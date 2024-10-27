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
        return f"Player at {format_ip(self.addr)}"

    def __init__(self, sock: socket.socket, addr: socket._RetAddress) -> None:
        self.state = Player.State.LOBBY
        self.room: GameRoom | None = None
        self.sock = sock
        self.addr = addr
        self.lock = threading.Lock()
        self.exitedException = self.ExitedException(
            self, f"{self} exited unexpectedly")

    def join(self, room: GameRoom) -> bool | None:
        self.room = room
        self.state = Player.State.WAITING
        return room.add_player(self)

    def leave(self) -> None:
        log.info(f"{self} left the room")
        self.state = Player.State.LOBBY
        if self.room is not None:
            self.room.remove_player(self)
        self.room = None

    def exit(self) -> None:
        self.state = Player.State.DISCONNECTED

    def send(self, msg: str) -> None:
        try:
            log.debug(f"Sending message to {self}: {msg}")
            self.sock.send(msg.encode("ascii"))
        except socket.error as e:
            log.error(f"Socket error: {e}")
            self.state = Player.State.DISCONNECTED
            raise self.exitedException
        except UnicodeEncodeError as e:
            log.error(f"Failed to encode message: {e}")
            self.state = Player.State.DISCONNECTED
            raise self.exitedException


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
        self._lock = threading.Lock()
        self.begin = threading.Event()
        self.finish = threading.Event()
        self.abort = threading.Event()
        self.clean = threading.Event()
        self.clean.set()

    def __len__(self) -> int:
        return len(self.players)

    def add_player(self, player: Player) -> bool | None:
        with self._lock:
            if player not in self.players:
                self.players.append(player)
            else:
                log.warning(f"{player} is already in the room")

    def remove_player(self, player: Player) -> None:
        with self._lock:
            if player in self.players:
                self.players.remove(player)
            else:
                log.warning(
                    f"Trying to remove {player} from room, but not found"
                )

    def start(self) -> None:
        raise NotImplementedError

    def reset(self) -> None:
        self.players = list[Player]()
        self.begin.clear()
        self.finish.clear()
        self.abort.clear()
        self.clean.set()

    def cleanup(self) -> None:
        for p in self.players:
            with p.lock:
                p.state = Player.State.LOBBY
                p.room = None

        self.reset()


class GuessGameRoom(GameRoom):
    def __init__(self) -> None:
        super().__init__()
        self.MAX_PLAYERS = 2

    def add_player(self, player: Player) -> bool:
        if len(self.players) == self.MAX_PLAYERS:
            player.send("3013 The room is full")
            return True

        super().add_player(player)

        with self._lock:
            self.clean.wait()
            if len(self.players) != self.MAX_PLAYERS:
                player.send("3011 Wait")
                return False

        self.start(player)
        return True

    def get_guess(self, player: Player) -> None:
        log.info(f"Waiting for guess from {player}")
        while True:
            try:
                with player.lock:
                    msg = player.sock.recv(1024).decode("ascii").split()
                    log.debug(f"Received message from {player}: {msg}")
                    if len(msg) == 2 and msg[0] == "/guess" and msg[1] in ["true", "false"]:
                        self.guesses[player] = msg[1] == "true"
                        self.got_guess[player].set()
                        return
                log.warning(f"Received invalid message from {player}: {msg}")
                player.send(
                    "4002 Unrecognized message")
            except UnicodeDecodeError as e:
                log.error(f"Unicode decode error: {e}")
                player.send(
                    "4002 Unrecognized message")
            except socket.error as e:
                log.error(f"Socket error: {e}")
                player.exit()
                raise player.exitedException

    def start(self, player: Player) -> None:
        try:
            assert len(self.players) == self.MAX_PLAYERS
        except AssertionError:
            log.error("Invalid number of players when starting game")
            return

        try:
            self.clean.clear()
            # Brodcast game start
            self.begin.set()
            log.info("Starting game in room with players: " +
                     ''.join([str(player) for player in self.players]))
            self.guesses: dict[Player, bool | None] = {
                player: None for player in self.players}
            self.got_guess = {player: threading.Event()
                              for player in self.players}

            log.info(f"Notifying \"starter\" {player}")
            with player.lock:
                player.state = Player.State.INGAME
            player.send(
                "3012 Game started. Please guess true or false")
            self.get_guess(player)

            # Wait for all players to finish
            for p in self.players:
                self.got_guess[p].wait()

            # Game main logic
            if self.abort.is_set():
                return

            with self._lock:
                if self.guesses[self.players[0]] == self.guesses[self.players[1]]:
                    # Tie
                    for p in self.players:
                        p.send("3023 The result is a tie")
                else:
                    ans = random.choice([True, False])
                    winner_id = self.guesses[self.players[1]] == ans

                    winner = self.players[winner_id]
                    loser = self.players[not winner_id]

                    winner.send("3021 You won this game")
                    loser.send("3022 You lost this game")

            for p in self.players:
                p.leave()

            self.finish.set()

            threading.Thread(target=self.cleanup).start()

        except Player.ExitedException as e:
            self.handle_player_exit(e)

    def handle_player_exit(self, e: Player.ExitedException) -> None:
        log.error(f"{e}")
        self.remove_player(e.player)
        self.abort.set()

        # Resolve other players
        for player in self.players:
            try:
                if player.state == Player.State.LOBBY:
                    continue

                if player.state == Player.State.WAITING:
                    player.send(
                        "3012 Game started. Please guess true or false")
                    with player.lock:
                        player.state = Player.State.INGAME
                    player.sock.recv(1024)

                # INGAME
                try:
                    player.send("3021 You won this game")
                except Player.ExitedException as ee:
                    log.error(f"{ee}")
                    self.remove_player(ee.player)
            except socket.error as se:
                log.error(f"Socket error: {se}")
                self.remove_player(player)

        threading.Thread(target=self.cleanup).start()


ROOM_COUNT = 8
rooms = [GuessGameRoom() for _ in range(ROOM_COUNT)]


def authenticate(sock: socket.socket, addr: socket._RetAddress, user_list: UserList) -> bool:
    log.info(f"Authenticating {format_ip(addr)}")
    try:
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
                log.warning(
                    f"Received invalid message from"
                    f"{format_ip(addr)}: {msg}"
                )
                sock.send("4002 Unrecognized message".encode("ascii"))
    finally:
        return authenticated


def handle_list(player: Player) -> None:
    log.info(f"{player} requested room list")
    player.send(
        f"3001 {len(rooms)} {' '.join([str(len(room)) for room in rooms])}"
    )


def handle_enter(player: Player, room_id_str: str) -> None:
    log.info(f"{player} requested to enter room {room_id_str}")
    room_id = int(room_id_str) - 1
    room = rooms[room_id]
    if player.join(room):
        return

    try:
        log.info(f"{player} is waiting for game to start")
        # Wait for game to start
        while not room.begin.is_set():
            if room.abort.is_set():
                player.leave()
                return

        # Game started
        log.info(f"Notifying {player}")
        with player.lock:
            player.state = Player.State.INGAME
        player.send(
            "3012 Game started. Please guess true or false")
        room.get_guess(player)

        # Wait for game to finish
        while not room.finish.is_set():
            if room.abort.is_set():
                break

        return

    except Player.ExitedException as e:
        room.handle_player_exit(e)


def handle_unknown_msg(player: Player, msg: str) -> None:

    log.warning(f"Received invalid message from {player}: {msg}")
    player.send("4002 Unrecognized message")


MSG_HANDLERS = {"/list": handle_list, "/enter": handle_enter}
MSG_LENGTHS = {"/list": 1, "/enter": 2}


def handle_client(sock: socket.socket, addr: socket._RetAddress, user_list: UserList) -> None:
    try:
        if not authenticate(sock, addr, user_list):
            log.error("Failed to authenticate user")
            return
    except socket.error as e:
        log.error(f"Socket error: {e}")

    player = Player(sock, addr)
    log.info(f"{player} successfully logged in")
    handle_lobby(player)


def handle_lobby(player: Player) -> None:
    sock = player.sock

    # Receive messages
    while True:
        try:
            msg = sock.recv(1024).decode("ascii")
            segs = msg.split()

            # "The server can detect “EOF” by a receive of 0 bytes."
            # https://docs.python.org/3/howto/sockets.html#creating-a-socket
            if not msg:  # Client EOF
                log.error(
                    f"Received empty message from {player}, disconnected"
                )
                sock.close()
                break

            log.info(f"Received message from {player}: {msg}")
            if segs[0] == "/exit" and len(segs) == 1:
                player.send("4001 Bye Bye")
                sock.close()
                break
            elif segs[0] in MSG_HANDLERS and len(segs) == MSG_LENGTHS[segs[0]]:
                MSG_HANDLERS[segs[0]](player, *segs[1:])
            else:
                handle_unknown_msg(player, msg)
        except UnicodeDecodeError as e:
            log.error(f"Unicode decode error: {e}")
            player.send("4002 Unrecognized message")
        except socket.error as e:
            log.error(f"Socket error: {e}")
            sock.close()
            player.exit()
            break
        except Player.ExitedException as e:
            log.error(f"{e}")
            break


def main() -> None:
    # Verify arguments
    if len(sys.argv) > 4 or len(sys.argv) < 3:
        print("Usage: python GameServer.py <port> <path/to/UserInfo.txt>")
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

    # Load user info
    try:
        user_info_path = Path(sys.argv[2])
        assert user_info_path.exists()
    except TypeError as e:
        log.critical(f"Invalid path: {e}")
        exit(1)
    except ValueError as e:
        log.critical(f"Invalid path: {e}")
        exit(1)
    except AssertionError:
        log.critical("File does not exist")
        exit(1)

    user_list = UserList(user_info_path)

    # Start server
    try:
        port = int(sys.argv[1])
        assert 0 <= port <= 65535

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(("", port))
        server_socket.listen(5)
    except AssertionError as e:
        log.critical(f"Invalid port: {e}")
        exit(1)
    except socket.error as e:
        log.critical(f"Socket error: {e}")
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
        threading.Thread(target=handle_client, args=(
            conn, addr, user_list)).start()


if __name__ == "__main__":
    main()
