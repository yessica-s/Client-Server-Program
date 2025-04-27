import sys 
import re
from socket import *
from threading import Lock, Thread, current_thread
from enum import Enum
from queue import Queue

class EXIT_CODES(Enum):
    CONFIG_FILE_ERROR = 5
    USAGE_ERROR = 4
    PORT_ERROR = 6


# Shared resource (counter to count the number of data packets received)
counter = 0
counter_lock = Lock()

BUFSIZE=1024

class Channel: 
    def __init__(self, name, port, capacity, socket):
        self.name = name
        self.port = port
        self.capacity = capacity
        self.socket = socket

        self.connected_clients = [] # connected clients. DOES NOT STORE QUEUE USERNAMES
        self.client_sockets = {} # client -> socket

        self.queue = Queue() # clients waiting to join
        self.queue_sockets = {} # client -> socket

class Server: 
    def __init__(self, afk_time, config_file): 
        self.afk_time = afk_time
        self.config_file = config_file
        self.channels = []
        self.channel_names = []
        self.channel_ports = []

    def load_config(self): # load the config file and check invalid lines
        listening_socket = None
        with open(self.config_file, 'r') as file: 
            while True:
                line = file.readline()

                if not line: # break when EOF reached
                    break

                line = line.strip() # remove leading or trailing whitespace
                channel = line.split(" ")

                if not len(channel) == 4: # too little/many arguments
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if not channel[0] == "channel":
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)
                
                channel_name = channel[1] # TODO: check any args empty strings???, check if config file None or empty???
                channel_port = channel[2]
                channel_capacity = channel[3]

                if not re.match("^[A-Za-z0-9_]*$", channel_name): # check channel only letters, numbers, underscores
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if channel_name in self.channel_names: # check channel name unique
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if not channel_port.isdigit(): # check port is integer
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                channel_port = int(channel[2]) # convert to int after checking

                if not (1024 <= channel_port <= 65535): # port out of range
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if channel_port in self.channel_ports: # check channel port unique
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if not channel_capacity.isdigit(): # check capacity is integer
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                channel_capacity = int(channel[3]) # convert to int after checking

                if not (1 <= channel_capacity <= 8): # capacity out of range
                    print("Error: Invalid configuration file.\n", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                listening_socket = self.start_server(channel_port)

                new_channel = Channel(channel_name, channel_port, channel_capacity, listening_socket)
                self.channels.append(new_channel)
                self.channel_names.append(channel_name)
                self.channel_ports.append(channel_port)

                print(f"Channel \"{channel_name}\" is created on port {channel_port}, with a capacity of {channel_capacity}.\n", file=sys.stdout)
                sys.stdout.flush()

            print("Welcome to chatserver.\n", file=sys.stdout)
            sys.stdout.flush()
        
        file.close()
        return listening_socket

    def start_server(self, port):
        listening_socket = socket(AF_INET, SOCK_STREAM)
        listening_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            listening_socket.bind(('', port))
        except Exception:
            print(f"Error: unable to listen on port {port}.\n", file=sys.stderr)
            exit(EXIT_CODES.PORT_ERROR.value)
        listening_socket.listen(5)
        
        return listening_socket 
    
    # Create a new thread for each channel
    def process_connections(self):
        for channel in self.channels:
            client_thread = Thread(target=self.handle_channel, args=(channel, ))
            client_thread.start()

    # Create a new thread for each client
    def handle_channel(self, channel):
        # TODO: muted clients, afk timer, counter thing from given code?
        # TODO: join threads when finished? 
        # TODO: remember to close sockets for clients
        while True: 
            client_socket, client_address = channel.socket.accept()
            client_thread = Thread(target=self.handle_client, args=(channel, client_socket, client_address))
            client_thread.start() 

    def handle_client(self, channel, client_socket, client_address):
        client_username = client_socket.recv(BUFSIZE).decode().strip() # get client username, sent automatically by client after connection
        
        # check username not already in channel
        with counter_lock:
            if client_username in channel.connected_clients: # duplicate username in connected list
                duplicate_username_message = f"[Server Message] Channel \"{channel.name}\" already has user {client_username}.\n"
                client_socket.sendall(duplicate_username_message.encode())  
                client_socket.close()
                return
            elif client_username in channel.queue: # duplicate username in queue
                duplicate_username_message = f"[Server Message] Channel \"{channel.name}\" already has user {client_username}.\n"
                client_socket.sendall(duplicate_username_message.encode())  
                client_socket.close()
                return
            else:      
                connected_message = f"Welcome to chatclient, {client_username}.\n"
                client_socket.sendall(connected_message.encode())

                connected = False # tracks whether client connected (T) or in queue (F)
                # Check capacity and queue/connect client
                if len(channel.connected_clients) == channel.capacity: # Maximum capacity, queue client
                    channel.queue.put(client_username)
                    channel.queue_sockets[client_username] = client_socket
                    users_ahead = channel.queue.qsize() - 1
                    print(f"[Server Message] You are in the waiting queue and there are {users_ahead} user(s) ahead of you.\n", file=sys.stdout)
                else: # Connect client
                    channel.connected_clients.append(client_username)
                    channel.client_sockets[client_username] = client_socket
                    print(f"[Server Message] {client_username} has joined the channel \"{channel.name}\".\n", file=sys.stdout)
                    connected = True
                
                sys.stdout.flush()

        self.handle_communication(channel, client_username, connected)

    def handle_communication(self, channel, client_username, connected):
        # continuously listen and send data to other clients in channel
        pass

    def main(self):
        listening_socket = self.load_config()
        self.process_connections()  

def usage_checking(arr): 
    config_file = None
    afk_time = 100 # default 100

    # TODO: need to check if values for anything are empty strings!!!, also for empty config file checked in server

    if len(sys.argv) not in (2,3): # too little/ too many arguments
        print("Usage: chatserver [afk_time] config_file\n", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    config_file = sys.argv[1] # default as only argument if afk_time not present

    if len(sys.argv) == 3: # afk_time argument present, need to check btwn 1 and 1000 inclusive
        if not sys.argv[1].isdigit(): # check afk_time is integer
            print("Usage: chatserver [afk_time] config_file\n", file=sys.stderr)
            exit(EXIT_CODES.USAGE_ERROR.value)
        
        afk_time = int(sys.argv[1])
        config_file = sys.argv[2] # if afk_time argument present, change to second argument

        if afk_time < 1 or afk_time > 1000: # out of range
            print("Usage: chatserver [afk_time] config_file\n", file=sys.stderr)
            exit(EXIT_CODES.USAGE_ERROR.value)

    # attempt to open the configuration file
    try:
        with open(config_file) as file:
            pass
    except FileNotFoundError:
        print("Error: Invalid configuration file.\n", file=sys.stderr)
        exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

    return config_file, afk_time

def main():
    config_file, afk_time = usage_checking(sys.argv)
    server = Server(afk_time, config_file)
    server.main() # server.load_config()

if __name__ == "__main__":
    main()