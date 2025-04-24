import sys
import re
from socket import *
from sys import stdout, stdin, argv, exit


class Channel:
    def __init__(self, name, port, capacity):
        self.name = name
        self.port = port
        self.capacity = capacity
        # self.clients = [] # connected clients
        # self.queue = [] # clients waiting to join


class Server:
    def __init__(self, afk_time, config_file):
        self.afk_time = afk_time
        self.config_file = config_file
        self.channels = []
        self.channel_names = []
        self.channel_ports = []

    def load_config(self):  # load the config file and check invalid lines
        with open(self.config_file, "r") as file:
            while True:
                line = file.readline()

                if not line:  # break when EOF reached
                    break

                line = line.strip()  # remove leading or trailing whitespace
                channel = line.split(" ")

                if not len(channel) == 4:  # too little/many arguments
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                if not channel[0] == "channel":
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                channel_name = channel[
                    1
                ]  # TODO: check any args empty strings???, check if config file None or empty???
                channel_port = channel[2]
                channel_capacity = channel[3]

                if not re.match(
                    "^[A-Za-z0-9_]*$", channel_name
                ):  # check channel only letters, numbers, underscores
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                if channel_name in self.channel_names:  # check channel name unique
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                if not channel_port.isdigit():  # check port is integer
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                channel_port = int(channel[2])  # convert to int after checking

                if not (1024 <= channel_port <= 65535):  # port out of range
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                if channel_port in self.channel_ports:  # check channel port unique
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                if not channel_capacity.isdigit():  # check capacity is integer
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                channel_capacity = int(channel[3])  # convert to int after checking

                if not (1 <= channel_capacity <= 8):  # capacity out of range
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(5)

                listening_socket = self.start_server(
                    channel_port
                )  # TODO: do something with listening socket???, accept connections???

                new_channel = Channel(channel_name, channel_port, channel_capacity)
                self.channels.append(new_channel)
                self.channel_names.append(channel_name)
                self.channel_ports.append(channel_port)

    def start_server(port):
        listening_socket = socket(AF_INET, SOCK_STREAM)
        listening_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            listening_socket.bind(("", port))
        except Exception:
            print(f"Error: unable to listen on port {port}.\n", file=sys.stderr)
            exit(6)
        listening_socket.listen(5)

        return listening_socket


def usage_checking(arr):
    config_file = None
    afk_time = 100  # default 100

    # TODO: need to check if values for anything are empty strings!!!, also for config file checked in server

    if len(sys.argv) not in (2, 3):  # too little/ too many arguments
        print("Usage: chatserver [afk_time] config_file\n", file=sys.stderr)
        exit(4)

    config_file = sys.argv[1]  # default as only argument if afk_time not present

    if (
        len(sys.argv) == 3
    ):  # afk_time argument present, need to check btwn 1 and 1000 inclusive
        if not sys.argv[1].isdigit():  # check afk_time is integer
            print("Usage: chatserver [afk_time] config_file\n", file=sys.stderr)
            exit(4)

        afk_time = int(sys.argv[1])
        config_file = sys.argv[
            2
        ]  # if afk_time argument present, change to second argument

        if afk_time < 1 or afk_time > 1000:  # out of range
            print("Usage: chatserver [afk_time] config_file\n", file=sys.stderr)
            exit(4)

    # attempt to open the configuration file
    try:
        with open(config_file) as file:
            pass
    except FileNotFoundError:
        print("Error: Invalid configuration file.\n", file=sys.stderr)
        exit(5)

    return config_file, afk_time


def main():
    config_file, afk_time = usage_checking(sys.argv)
    server = Server(afk_time, config_file)
    server.load_config()


if __name__ == "__main__":
    main()
