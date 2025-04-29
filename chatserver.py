import sys, re
from socket import *
from threading import Lock, Thread, Timer, current_thread
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

        self.disconnected_clients = {} # stores client -> True for clients that are disconnected

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
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if not channel[0] == "channel":
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)
                
                channel_name = channel[1] # TODO: check any args empty strings???, check if config file None or empty???
                channel_port = channel[2]
                channel_capacity = channel[3]

                if not re.match("^[A-Za-z0-9_]*$", channel_name): # check channel only letters, numbers, underscores
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if channel_name in self.channel_names: # check channel name unique
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if not channel_port.isdigit(): # check port is integer
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                channel_port = int(channel[2]) # convert to int after checking

                if not (1024 <= channel_port <= 65535): # port out of range
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if channel_port in self.channel_ports: # check channel port unique
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                if not channel_capacity.isdigit(): # check capacity is integer
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                channel_capacity = int(channel[3]) # convert to int after checking

                if not (1 <= channel_capacity <= 8): # capacity out of range
                    print("Error: Invalid configuration file.", file=sys.stderr)
                    exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

                listening_socket = self.start_server(channel_port)

                new_channel = Channel(channel_name, channel_port, channel_capacity, listening_socket)
                self.channels.append(new_channel)
                self.channel_names.append(channel_name)
                self.channel_ports.append(channel_port)

                print(f"Channel \"{channel_name}\" is created on port {channel_port}, with a capacity of {channel_capacity}.", file=sys.stdout)
                sys.stdout.flush()

            print("Welcome to chatserver.", file=sys.stdout)
            sys.stdout.flush()
        
        file.close()
        return listening_socket

    def start_server(self, port):
        listening_socket = socket(AF_INET, SOCK_STREAM)
        listening_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            listening_socket.bind(('', port))
        except Exception:
            print(f"Error: unable to listen on port {port}.", file=sys.stderr)
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
        while True: 
            client_socket, client_address = channel.socket.accept()
            client_thread = Thread(target=self.handle_client, args=(channel, client_socket)) # removed client_address command
            client_thread.start() 

    def handle_client(self, channel, client_socket): # removed client_address arg
        client_username = client_socket.recv(BUFSIZE).decode().strip() # get client username, sent automatically by client after connection

        # check username not already in channel
        with counter_lock:
            if client_username in channel.connected_clients or client_username in channel.queue: # duplicate username in connected list or queue
                duplicate_username_message = f"[Server Message] Channel \"{channel.name}\" already has user {client_username}."
                client_socket.sendall(duplicate_username_message.encode())  
                client_socket.close()
                return
            else:      
                connected_message = f"Welcome to chatclient, {client_username}."
                client_socket.sendall(connected_message.encode())

                # Check capacity and queue/connect client
                if len(channel.connected_clients) == channel.capacity: # Maximum capacity, queue client
                    channel.queue.put(client_username)
                    channel.queue_sockets[client_username] = client_socket
                    users_ahead = channel.queue.qsize() - 1

                    # Notify client
                    message = f"[Server Message] You are in the waiting queue and there are {users_ahead} user(s) ahead of you."
                    client_socket.sendall(message.encode())

                else: # Connect client
                    channel.connected_clients.append(client_username)
                    channel.client_sockets[client_username] = client_socket

                    # Notify client and server stdout
                    self.notify_connected_client(client_username, channel.name, client_socket)

                sys.stdout.flush()

        self.handle_communication(channel, client_username)

    def handle_communication(self, channel, client_username):
        # Continuously listen and send data to other clients in channel

        # TODO: any time client disconnects:
        # - from queue: 
        # - from connected: call message method and then disconnect method
        # DONE - from AFK: call timeout method and then disconnect method
        
        # Get client socket
        sock = None
        with counter_lock:
            if client_username in channel.connected_clients: # connected
                sock = channel.client_sockets[client_username]
            else: # queued
                sock = channel.queue_sockets[client_username]

        while True: # Queue Client 
            with counter_lock:
                queue_clients = list(channel.queue)
                if client_username not in queue_clients: # if left queue, break out of this loop 
                    break
            data = sock.recv(BUFSIZE)
            if not data:
                # TODO: do something, client disconnected from queue? 
                break
            # TODO: do stuff with data
            # print(data.decode().strip(), file=sys.stdout)

        # Check if somehow disconnected while being moved from queue - connected 
        with counter_lock:
            if client_username not in channel.connected_clients: 
                # TODO: client disconnected from queue?
                return  
            
        while True: # Connected Client
            # Start timer for afk
            timer = Timer(self.afk_time, self.timeout, args=(channel, client_username))
            timer.start()
            if channel.disconnected_clients.get(client_username) == True: 
                break # client to be disconnected - break and proceed to disconnect function
            data = sock.recv(BUFSIZE)
            timer.cancel() # Cancel timer since data received
            if not data:
                break
            # TODO: do stuff with data
            # print(data.decode().strip(), file=sys.stdout)

        # handle disconnection, update queue, etc.
        self.disconnect(channel, client_username)

    def disconnect(self, channel, client_username):
        with counter_lock:
            # If client disconnected from connected list
            if client_username in channel.connected_clients:
                # Remove client from list and from socket dict
                channel.connected_clients.remove(client_username) # remove from connected clients list
                socket = channel.client_sockets[client_username] # get socket for each client
                channel.client_sockets.pop(client_username) # remove from connected sockets list
                socket.close() # close socket
            else: # Client disconnected from queue
                # remove from queue by dequeueing and enqueing all except removed client
                queued_clients = []
                while not channel.queue.empty():
                    current = channel.queue.get()
                    if not current == client_username:
                        queued_clients.append(current)
                for item in queued_clients: # re-enqueue remaining clients in order
                    channel.queue.put(item)

                # channel.queue.queue.remove(client_username) # remove from queue
                socket = channel.queue_sockets[client_username]
                channel.queue_sockets.pop(client_username) # remove from queue sockets
                socket.close() # close socket

            # If empty spot in channel (connected client disconnected) and queue not empty, promote client from queue
            if len(channel.connected_clients) < channel.capacity and not channel.queue.empty(): # If there is client in queue
                new_client_username = channel.queue.get() # remove from queue
                new_client_socket = channel.queue_sockets[new_client_username] # get socket from dict
                channel.queue_sockets.pop(new_client_username) # remove from dict

                # add to connected list
                channel.connected_clients.append(new_client_username)
                channel.client_sockets[new_client_username] = new_client_socket

                # Notify client and server stdout that new client joined channel
                self.notify_connected_client(new_client_username, channel.name, new_client_socket)

                # Update user ahead message to queue clients
                users_ahead = 0 

                queued_clients = []
                while not channel.queue.empty():
                    current = channel.queue.get()
                    queued_clients.append(current)

                    sock = channel.queue_sockets[current] # get socket
                    message = f"[Server Message] You are in the waiting queue and there are {users_ahead} user(s) ahead of you."
                    sock.sendall(message.encode())
                    
                    users_ahead += 1 # increment number of users ahead

                for item in queued_clients: # re-enqueue remaining clients in order
                    channel.queue.put(item)

    def timeout(self, channel, client_username):
        afk_message = f"[Server Message] {client_username} went AFK in channel \"{channel.name}\"."
        
        # Send message to chatserver stdout
        print(afk_message, file=sys.stdout)
        sys.stdout.flush()

        with counter_lock:
            # Send message to connected clients (including client about to be disconnected)
            for client in channel.connected_clients: 
                socket = channel.client_sockets[client] # get socket for each client
                socket.sendall(afk_message.encode()) # send   

            channel.disconnected_clients[client_username] = True # assign it as disconnected so disconnect function called in handle_comms  
        
        return # disconnect and socket and thread close handled in disconnect function

    def notify_connected_client(self, username, channel_name, socket):
        print(f"[Server Message] {username} has joined the channel \"{channel_name}\".", file=sys.stdout)

        message = f"[Server Message] You have joined the channel \"{channel_name}\"."
        socket.sendall(message.encode())
        
    def main(self):
        listening_socket = self.load_config()
        self.process_connections()  

def usage_checking(arr): 
    config_file = None
    afk_time = 100 # default 100

    # TODO: need to check if values for anything are empty strings!!!, also for empty config file checked in server

    if len(sys.argv) not in (2,3): # too little/ too many arguments
        print("Usage: chatserver [afk_time] config_file", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    config_file = sys.argv[1] # default as only argument if afk_time not present

    if len(sys.argv) == 3: # afk_time argument present, need to check btwn 1 and 1000 inclusive
        if not sys.argv[1].isdigit(): # check afk_time is integer
            print("Usage: chatserver [afk_time] config_file", file=sys.stderr)
            exit(EXIT_CODES.USAGE_ERROR.value)
        
        afk_time = int(sys.argv[1])
        config_file = sys.argv[2] # if afk_time argument present, change config_file to second argument

        if afk_time < 1 or afk_time > 1000: # out of range
            print("Usage: chatserver [afk_time] config_file", file=sys.stderr)
            exit(EXIT_CODES.USAGE_ERROR.value)

    # Attempt to open the configuration file
    try:
        with open(config_file) as file:
            pass
    except FileNotFoundError:
        print("Error: Invalid configuration file.", file=sys.stderr)
        exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

    return config_file, afk_time

def main():
    config_file, afk_time = usage_checking(sys.argv)
    server = Server(afk_time, config_file)
    server.main() # server.load_config()

if __name__ == "__main__":
    main()