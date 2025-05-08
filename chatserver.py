import os
import sys 
from sys import stdin, stdout
import re
from socket import *
from threading import Lock, Thread, Timer, current_thread
from enum import Enum
from queue import Queue

class EXIT_CODES(Enum):
    CONFIG_FILE_ERROR = 5
    USAGE_ERROR = 4
    PORT_ERROR = 6

quit = False
quit_from_queue = False

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

        self.connected_clients = [] # connected clients
        self.client_sockets = {} # client -> socket

        self.queue = Queue() # clients waiting to join
        self.queue_sockets = {} # client -> socket
        self.queue_clients = 0 # number of clients in queue
        self.queue_clients_usernames = [] # list of queue client usernames

        self.disconnected_clients = [] # stores client -> True for clients that should be disconnected after afk timeout

class Server: 
    def __init__(self, afk_time, config_file): 
        self.afk_time = afk_time
        self.config_file = config_file
        self.channels = []
        self.channel_names = []
        self.channel_ports = []

    def load_config(self): # load the config file and check invalid lines
        names = []
        ports = []
        capacities = []

        # Check if file empty
        if os.path.getsize(self.config_file) == 0:
            print("Error: Invalid configuration file.", file=sys.stderr)
            exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

        with open(self.config_file, 'r') as file: 
            while True:
                line = file.readline()

                if not line: # break when EOF reached
                    break

                # TODO: special symbols at end
                # if '\r\n' in line or "\^M\n" in line: # '\r\n' in line or '^M' in line: # check for trailing characters e.g. ^M #  
                #     print("Error: Invalid configuration file.", file=sys.stderr)
                #     exit(EXIT_CODES.CONFIG_FILE_ERROR.value)

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

                names.append(channel_name)
                ports.append(channel_port)
                capacities.append(channel_capacity)

        # check each port is connectable and open a socket for it
        length = len(names)

        for i in range(0, length):
            listening_socket = self.start_server(ports[i])

            new_channel = Channel(names[i], ports[i], capacities[i], listening_socket)
            self.channels.append(new_channel)
            self.channel_names.append(names[i])
            self.channel_ports.append(ports[i])

        # print that channels created successfully
        for i in range(0, length):
            print(f"Channel \"{self.channels[i].name}\" is created on port {self.channels[i].port}, with a capacity of {self.channels[i].capacity}.", file=sys.stdout)
            sys.stdout.flush()
        
        print("Welcome to chatserver.", file=sys.stdout)
        sys.stdout.flush()
        
        file.close()
        return

    def start_server(self, port):
        listening_socket = socket(AF_INET, SOCK_STREAM)
        listening_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        try:
            listening_socket.bind(('', port))
        except Exception:
            print(f"Error: unable to listen on port {port}.", file=sys.stderr, flush=True)
            
            exit(EXIT_CODES.PORT_ERROR.value)
        listening_socket.listen(5)
        
        return listening_socket 
    
    # Create a new thread for each channel
    def process_connections(self):

        stdin_thread = Thread(target=self.handle_stdin, daemon=True)
        stdin_thread.start()

        for channel in self.channels:
            client_thread = Thread(target=self.handle_channel, args=(channel, ))
            client_thread.start()

    def handle_stdin(self):
        while True:
            try: 
                for line in stdin:
                    line = line.strip("\n")
                    commands = line.split(" ")
                    if commands[0] == "/kick" or commands[0] == "/kick\n":
                        commands = line.split(" ", maxsplit=2)
                        if len(commands) != 3: 
                            print("Usage: /kick channel_name client_username", file=sys.stdout, flush=True)
                        elif commands[1] == "" or commands[1] == " " or commands[2] == "" or commands[2] == " ":
                            print("Usage: /kick channel_name client_username", file=sys.stdout, flush=True)
                        elif " " in commands[1] or " " in commands[2]:
                            print("Usage: /kick channel_name client_username", file=sys.stdout, flush=True)
                        elif not re.match(r'^[\x21-\x7E]*$', commands[1]) or not re.match(r'^[\x21-\x7E]*$', commands[2]): # does not allow space, allows new lines # \n after *
                            print("Usage: /kick channel_name client_username", file=sys.stdout, flush=True)
                        else:
                            self.kick_command(commands[1], commands[2])
                    elif commands[0] == "/shutdown" or commands[0] == "/shutdown\\n": # or commands[0] == "/shutdown\n":
                        if len(commands) != 1: 
                            print("Usage: /shutdown", file=sys.stdout, flush=True)
                        elif not re.match(r'^[\x21-\x7E]*$', commands[0]) or "\\n" in commands[0]: # does not allow space, allows new lines # \n after *
                            print("Usage: /shutdown", file=sys.stdout, flush=True)
                        else:
                            print(f"[Server Message] Server shuts down.", file=sys.stdout, flush=True)
                            os._exit(0)
                    elif commands[0] == "/mute" or commands[0] == "/mute\\n" or commands[0] == "\mute\n":
                        commands = line.split(" ", maxsplit=4)
                        if len(commands) != 4:
                            print("Usage: /mute channel_name client_username duration", file=sys.stdout, flush=True)
                        elif commands[1] == "" or " " in commands[1] or commands[2] == "" or " " in commands[2] or commands[3] == "" or " " in commands[3]:
                            print("Usage: /mute channel_name client_username duration", file=sys.stdout, flush=True)
                        elif not re.match(r'^[\x21-\x7E]*$', commands[1]) or not re.match(r'^[\x21-\x7E]*$', commands[2]) or not re.match(r'^[\x21-\x7E]*$', commands[3]):
                            print("Usage: /mute channel_name client_username duration", file=sys.stdout, flush=True)
                        else:
                            self.mute_command(commands[1], commands[2], commands[3])
                    elif commands[0] == "/empty" or commands[0] == "/empty\\n" or commands[0] == "/empty\n":
                        commands = line.split(" ", maxsplit=1)
                        if len(commands) != 2:
                            print("Usage: /empty channel_name", file=sys.stdout, flush=True)
                        elif commands[1] == "" or commands[1] == " ": # channel name is space
                            print("Usage: /empty channel_name", file=sys.stdout, flush=True)
                        elif " " in commands[1]:
                            print("Usage: /empty channel_name", file=sys.stdout, flush=True)
                        elif not re.match(r'^[\x21-\x7E]*$', commands[1]): # does not allow space, allows new lines # \n after *
                            print("Usage: /empty channel_name", file=sys.stdout, flush=True)
                        # elif commands[1].rstrip("\n") != commands[1].rstrip():
                        #     print("Usage: /empty channel_name", file=sys.stdout, flush=True)
                        else:
                            self.empty_command(commands[1])
            except KeyboardInterrupt:
                # TODO: server disconnect
                pass

    def get_channel(self, channel_name): 
        # Check channel exists
        if not channel_name in self.channel_names:
            print(f"[Server Message] Channel \"{channel_name}\" does not exist.", file=sys.stdout, flush=True)
    
        # Get channel object and return
        channel = None
        for current_channel in self.channels:
            if current_channel.name == channel_name:
                channel = current_channel
                break
        
        return channel

    def mute_command(self, channel_name, client_username, duration):
        # Check channel exists
        channel = self.get_channel(channel_name)
        if channel is None:
            return
        
        # Check connected client in channel
        with counter_lock:
            if not client_username in channel.connected_clients:
                print(f"[Server Message] {client_username} is not in the channel.", file=sys.stdout, flush=True)
                return
        
        # Check duration positive integer
        try:
            duration = int(duration)
            if duration <= 0: 
                raise ValueError
        except ValueError:
            print("[Server Message] Invalid mute duration.", file=sys.stdout, flush=True)
            return
    
        # Print to stdout
        print(f"[Server Message] Muted {client_username} for {duration} seconds.", file=sys.stdout, flush=True)

        # Notify client and connected clients
        message = f"[Server Message] You have been muted for {duration} seconds."
        with counter_lock:
            socket = channel.client_sockets.get(client_username)
            socket.sendall(message.encode())

            message = f"[Server Message] {client_username} has been muted for {duration} seconds."
            for other_client in channel.connected_clients:
                if not other_client == client_username:
                    other_socket = channel.client_sockets.get(other_client)
                    other_socket.sendall(message.encode())

        # Client handles mute functionality   

    def kick_command(self, channel_name, client_username):
        # Check channel exists
        channel = self.get_channel(channel_name)
        if channel is None:
            return

        # Check connected client in channel
        with counter_lock:
            if not client_username in channel.connected_clients:
                print(f"[Server Message] {client_username} is not in the channel.", file=sys.stdout, flush=True)
                return
            
        # Notify kicked user
        message = "[Server Message] You are removed from the channel."
        with counter_lock:
            socket = channel.client_sockets.get(client_username) # Get kicked client socket
            socket.sendall(message.encode())

            # Handle kicking - Remove client from list and from socket dict
            channel.connected_clients.remove(client_username) # remove from connected clients list
            channel.client_sockets.pop(client_username) # remove from connected sockets list
            socket.close() # close socket

        # Print to stdout
        print(f"[Server Message] Kicked {client_username}.", file=sys.stdout, flush=True)

        message = f"[Server Message] {client_username} has left the channel."
        with counter_lock:
            for other_client in channel.connected_clients: # Notify connected clients
                other_socket = channel.client_sockets.get(other_client)
                other_socket.sendall(message.encode())
        
            for other_client in channel.queue_clients_usernames: # Notify queue'd clients
                other_socket = channel.queue_sockets.get(other_client)
                other_socket.sendall(message.encode())  

    def empty_command(self, channel_name):
        # Check channel exists
        channel = self.get_channel(channel_name)
        if channel is None:
            return
        
        message = "[Server Message] You are removed from the channel."
        # Disconnect each client
        with counter_lock:
            for client_username in list(channel.connected_clients):
                # Get socket
                socket = channel.client_sockets[client_username]
                socket.sendall(message.encode())

                # Remove client from list and from socket dict
                channel.connected_clients.remove(client_username) # remove from connected clients list
                socket = channel.client_sockets[client_username] # get socket for each client
                channel.client_sockets.pop(client_username) # remove from connected sockets list
                socket.close() # close socket
        
        print(f"[Server Message] \"{channel_name}\" has been emptied.", file=sys.stdout, flush=True)

        # Promote clients from queue
        with counter_lock:
            for i in range(0, channel.capacity):
                self.promote_from_queue(channel)

    # Create a new thread for each client
    def handle_channel(self, channel):
        while True: 
            client_socket, client_address = channel.socket.accept()
            client_thread = Thread(target=self.handle_client, args=(channel, client_socket, None, False)) # removed client_address command
            client_thread.start() 

    def handle_client(self, channel, client_socket, switch_client_username, switch): # removed client_address arg
        client_username = None
        if switch:
            client_username = switch_client_username
            switch = False
        else: 
            client_username = client_socket.recv(BUFSIZE).decode().strip() # get client username, sent automatically by client after connection

        # check username not already in channel
        with counter_lock:
            if client_username in channel.connected_clients or channel.queue_sockets.get(client_username) is not None: # client_username in channel.queue: # duplicate username in connected list or queue
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
                    channel.queue_clients += 1 # increment number of clients in Queue
                    channel.queue_clients_usernames.append(client_username)

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
        return

    def handle_communication(self, channel, client_username):
        # Continuously listen and send data to other clients in channel
        global quit
        global quit_from_queue
        target_client = None
        file_path = None
        
        # Get client socket
        sock = None
        with counter_lock:
            if client_username in channel.connected_clients: # connected
                sock = channel.client_sockets[client_username]
            else: # queued
                sock = channel.queue_sockets[client_username]

        data = None

        while True: # Queue Client 
            with counter_lock:
                if channel.queue_sockets.get(client_username) is None: # left queue TODO: redundant because how would it be removed
                    break

            data = sock.recv(BUFSIZE)

            if not data: # client disconnected
                self.disconnect(channel, client_username, False) 
                self.promote_from_queue(channel)
                channel.queue_clients -= 1 # decrement number of clients in Queue
                return
            else:
                data_decoded = data.decode().strip()
                if data_decoded == "/quit" or data_decoded == "/quit\n":
                    quit_from_queue = True
                    self.disconnect(channel, client_username)
                    self.promote_from_queue(channel)
                    return
                elif data_decoded == "/list" or data_decoded == "/list\n":
                    self.list_command(sock)
                elif data_decoded[0] == "/switch":
                    self.switch_command(sock, channel, commands, client_username, True)
            
        # Check if somehow disconnected while being moved from queue - connected 
        with counter_lock:
            if client_username not in channel.connected_clients: 
                self.disconnect(channel, client_username, False)
                self.promote_from_queue(channel)
                return  
            
        # if anything sent since promoted to queue: print it out, TODO: problem is that if this is a command itll just print it
        if data is not None:
            self.print_message(data, client_username, channel)

        while True: # Connected Client
            # Start timer for afk
            timer = Timer(self.afk_time, self.timeout, args=(channel, client_username))
            timer.start()

            if client_username in channel.disconnected_clients: # client to be disconnected due to AFK
                self.disconnect(channel, client_username, False)
                self.promote_from_queue(channel)
                return

            data = sock.recv(BUFSIZE)
            timer.cancel() # Cancel AFK timer since data received

            if not data:
                break

            data_decoded = data.decode().strip()
            commands = data_decoded.split(" ")

            if data_decoded == "/quit" or data_decoded == "/quit\n":
                quit = True
                self.disconnect(channel, client_username, False)
                self.promote_from_queue(channel)
                return
            elif data_decoded == "/list" or data_decoded == "/list\n":
                self.list_command(sock)
            elif commands[0] == "/whisper":
                self.whisper_command(sock, channel, commands, client_username)
            elif commands[0] == "/switch":
                if not self.switch_command(sock, channel, commands, client_username, False):
                    # didn't work
                    continue
                else:
                    new_channel = commands[1]
                    for channels in self.channels:
                        if channels.name == new_channel:
                            new_channel = channels
                            break
                        
                    self.disconnect(channel, client_username, True)
                    self.handle_client(new_channel, sock, client_username, True)
                    return
            elif commands[0] == "/send":
                target_client = commands[1] # store the target client username
                file_path = commands[2].strip()
                self.send_command(sock, channel, commands, client_username)
                continue
            elif data_decoded == "[Client Message] Received":
                continue
                # elif data_decoded == "[Client Message] Ready" or data_decoded == "[Client Message] File Transfer Failed" or data_decoded == "[Client Message] Received": 
                #     continue # part of file transfer process - handled in sending client's thread  
            elif commands[0] == "[FileSize]": # client file sending handled in send function
                self.handle_file_transfer(channel, commands, target_client, file_path, sock, client_username)
            else: 
                self.print_message(data, client_username, channel)

        # handle disconnection, update queue, etc.
        self.disconnect(channel, client_username, False)
        self.promote_from_queue(channel)
        return
    

    def handle_file_transfer(self, channel, commands, target_client, file_path, sock, client_username):
        file_size = int(commands[1])

        file_data = b""

        while len(file_data) < file_size: 
            current = sock.recv(min(BUFSIZE, file_size - len(file_data)))
            if not current: # Failed
                message = f"[Server Message] Failed to send \"{file_path}\" to {target_client}"
                sock = channel.client_sockets.get(client_username)
                sock.sendall(message.encode())
                continue
            file_data += current

        # Received, transfer to target client now
        parts = file_path.split('/')
        basename = parts[-1]

        target_socket = channel.client_sockets.get(target_client)
        message = f"[Server Message] FileSize {basename} {file_size}"
        target_socket.sendall(message.encode()) # Send file size

        # wait for response from client
        ack = target_socket.recv(BUFSIZE).decode().strip()
        if ack == "[Client Message] Ready":
            target_socket.sendall(file_data)
        
            # print("waiting for data",flush=True)
            # data = target_socket.recv(BUFSIZE).decode().strip()
            # print("got it", flush=True)

            # if data == "[Client Message] File Transfer Failed":
            #     message = f"[Server Message] Failed to send \"{file_path}\" to {target_client}"
            #     sock = channel.client_sockets.get(client_username)
            #     sock.sendall(message.encode())
            #     continue
            # elif data == "[Client Message] Received":
            #     print("recevied the received message", flush=True)
            #     pass

            # Send sent message to client
            message = f"[Server Message] Sent \"{file_path}\" to {target_client}."
            sock.sendall(message.encode())

            # Send message to server stdout and receiver
            parts = file_path.split('/')
            basename = parts[-1]

            message = f"[Server Message] {client_username} sent \"{basename}\" to {target_client}."
            print(message, file=sys.stdout, flush=True)
            target_socket.sendall(message.encode())

            target_client = None
            file_path = None
        else: 
            self.print_message(ack, client_username, channel)

    def disconnect(self, channel, client_username, switch):
        message = f"[Server Message] {client_username} has left the channel."

        # If not emptied
        with counter_lock:
            if not client_username in channel.disconnected_clients: # if not AFK client
                if client_username in channel.connected_clients or client_username in channel.queue_clients_usernames: 
                    print(message)
                    sys.stdout.flush()

        global quit
        global quit_from_queue

        with counter_lock:
            # send to all clients in channel
            if quit_from_queue: 
                pass
            elif quit:
                for other_client in channel.connected_clients: 
                    if other_client == client_username:
                        continue
                    current_socket = channel.client_sockets.get(other_client)
                    current_socket.sendall(message.encode())
            elif client_username in channel.disconnected_clients:
                pass # don't send "left" message to other clients if AFK
            elif switch:
                for other_client in channel.connected_clients: # don't inform switching client in switch
                    if not other_client == client_username: 
                        current_socket = channel.client_sockets.get(other_client)
                        current_socket.sendall(message.encode())
            elif client_username in channel.connected_clients: # or client_username in channel.queue_clients_usernames:
                for other_client in channel.connected_clients: 
                    current_socket = channel.client_sockets.get(other_client)
                    current_socket.sendall(message.encode())

            # Remove from disconnected client list in case later on another client with same name disconnects
            if client_username in channel.disconnected_clients:
                channel.disconnected_clients.remove(client_username)
            # If client disconnected from connected list
            if client_username in channel.connected_clients:
                # Remove client from list and from socket dict
                channel.connected_clients.remove(client_username) # remove from connected clients list
                socket = channel.client_sockets[client_username] # get socket for each client
                channel.client_sockets.pop(client_username) # remove from connected sockets list
                if not switch: # don't close socket in switching
                    socket.close() # close socket
            elif client_username in channel.queue_clients_usernames: # Client disconnected from queue
                # remove from queue by dequeueing and enqueing all except removed client
                queued_clients = []
                channel.queue_clients_usernames.remove(client_username)
                # channel.queue_clients -= 1 this is done in handle comms function
                while not channel.queue.empty():
                    current = channel.queue.get()
                    if not current == client_username:
                        queued_clients.append(current)
                for item in queued_clients: # re-enqueue remaining clients in order
                    channel.queue.put(item)

                # channel.queue.queue.remove(client_username) # remove from queue
                socket = channel.queue_sockets[client_username]
                channel.queue_sockets.pop(client_username) # remove from queue sockets
                if not switch: # don't close socket in switching
                    socket.close() # close socket
                
    def promote_from_queue(self, channel):
        # If empty spot in channel (connected client disconnected) and queue not empty, promote client from queue
        if len(channel.connected_clients) < channel.capacity and not channel.queue.empty(): # If there is client in queue
            new_client_username = channel.queue.get() # remove from queue
            new_client_socket = channel.queue_sockets[new_client_username] # get socket from dict
            channel.queue_sockets.pop(new_client_username) # remove from dict
            channel.queue_clients -= 1 # decrement number of clients in Queue
            channel.queue_clients_usernames.remove(new_client_username)

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
    
    def print_message(self, data, client_username, channel):
        message = data.decode().strip()
        start_of_message = f"[{client_username}]"
        message_to_send = start_of_message + " " + message
        # send to all clients in channel
        for other_client in channel.connected_clients: 
            current_socket = channel.client_sockets.get(other_client)
            current_socket.sendall(message_to_send.encode())

        # print to stdout of server
        print(message_to_send, file=sys.stdout)
        sys.stdout.flush()
        
        return

    def timeout(self, channel, client_username):
        afk_message = f"[Server Message] {client_username} went AFK in channel \"{channel.name}\"."
        
        # Send message to chatserver stdout
        print(afk_message, file=sys.stdout, flush=True)

        with counter_lock:
            # Send message to connected clients (including client about to be disconnected)
            for client in channel.connected_clients:
                socket = channel.client_sockets[client] # get socket for each client
                socket.sendall(afk_message.encode()) # send   

            channel.disconnected_clients.append(client_username) # assign it as disconnected due to AFK so disconnect function called in handle_comms  
        
        return # disconnect and socket and thread close handled in disconnect function

    def notify_connected_client(self, username, channel_name, socket):
        print(f"[Server Message] {username} has joined the channel \"{channel_name}\".", file=sys.stdout)
        sys.stdout.flush()

        message = f"[Server Message] You have joined the channel \"{channel_name}\"."
        socket.sendall(message.encode())

    def send_command(self, sock, channel, commands, client_username):
        # commands in format: [/send, target_client_username, file_path]

        # Same client
        if client_username == commands[1]: 
            message = "[Server Message] Cannot send file to yourself."
            sock.sendall(message.encode())
            return

        # Client doesn't exist
        client_exists = True
        if not commands[1] in channel.connected_clients:
            message = f"[Server Message] {commands[1]} is not in the channel."
            sock.sendall(message.encode())
            client_exists = False

        file_path = commands[2]
        
        message = "[Server Message] Start transmission."
        sock.sendall(message.encode())

        # Client checks if file path can be opened

        # File size and everything handled by recv
        # Get file size
        # data = sock.recv(BUFSIZE).decode().strip()

    # creates output for client when client sends /list command
    def list_command(self, sock):
        for channel in self.channels:
            message = f"[Channel] {channel.name} {channel.port} Capacity: {len(channel.connected_clients)}/{channel.capacity}, Queue: {channel.queue_clients}\n"
            sock.sendall(message.encode())

    def whisper_command(self, sock, channel, commands, client_username): 
        # commands is arr in format ["/whisper", client_username, chat_message]

        # Target client not in channel
        if not commands[1] in channel.connected_clients: 
            message = f"[Server Message] {commands[1]} is not in the channel."
            sock.sendall(message.encode())
        else: # Client in channel
            message = f"[{client_username} whispers to you] {commands[2]}"
            target_socket = channel.client_sockets.get(commands[1])
            target_socket.sendall(message.encode())

            message = f"[{client_username} whispers to {commands[1]}] {commands[2]}"

            print(message, file=sys.stdout) # successful whisper message to server stdout
            sys.stdout.flush()

            sock.sendall(message.encode()) # successful whisper message to sender client
        
    def switch_command(self, sock, channel, commands, client_username, queue_client):
        # TODO: create function like handle client separate for switch and debug

        new_channel = commands[1]
        # print(new_channel, flush=True)
        if new_channel not in self.channel_names:
            message = f"[Server Message] Channel \"{new_channel}\" does not exist."
            sock.sendall(message.encode())
            return False
        
        # Get channel object using name
        for current_channel in self.channels:
            if current_channel.name == new_channel:
                new_channel = current_channel
                break

        # check if client exists already
        if client_username in new_channel.connected_clients or client_username in new_channel.queue_clients_usernames:
            message = f"[Server Message] Channel \"{new_channel.name}\" already has user {client_username}."
            sock.sendall(message.encode())
            return False
        
        return True
        
        # self.disconnect(channel, client_username)
    
        # Switch to go ahead
        


        # if not self.handle_client(new_channel, sock, True): # Failed due to duplicate username, stay in current channel
        #     return False
        
        # Switch has worked - send messages
        # self.disconnect(channel, client_username)

        # message = f"[Server Message] {client_username} has left the channel."
        # print(message, file=sys.stdout, flush=True)
        # if not queue_client: 
        #     with counter_lock:
        #         for client in channel.connected_clients: 
        #             if not client == client_username: #
        #                 socket = channel.client_sockets[client] # get socket for each client
        #                 socket.sendall(message.encode()) # send


    def main(self):
        self.load_config()
        self.process_connections()  

def usage_checking(arr): 
    config_file = None
    afk_time = 100 # default 100

    # TODO: need to check if values for anything are empty strings!!!

    if len(sys.argv) not in (2,3): # too little/ too many arguments
        print("Usage: chatserver [afk_time] config_file", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    # Check empty arguments
    for arg in sys.argv:
        if arg == "" or arg == " ":
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