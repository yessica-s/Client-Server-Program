import datetime
import sys, os, time
from socket import *
from sys import stdout, stdin, argv, exit
import re
from enum import Enum
from threading import Thread

BUFSIZE = 1024
sock = None
quit = False
mute = False
mute_duration = 0
mute_counter = 0
file_path = None
client_doesnt_exist = False
sending = True

class EXIT_CODES(Enum):
    USAGE_ERROR = 3
    PORT_CHECK_ERROR = 7
    DUPLICATE_USERNAME_ERROR = 2
    DISCONNECT_ERROR = 8


def usage_checking():
    if len(sys.argv) < 3 or len(sys.argv) > 3:  # Not enough/too many arguments
        print("Usage: chatclient port_number client_username", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    if sys.argv[1] == "" or sys.argv[2] == "":  # empty strings
        print("Usage: chatclient port_number client_username", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    # check client username is space
    if sys.argv[1] == " " or sys.argv[2] == " ":  # empty strings
        print("Usage: chatclient port_number client_username", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    # TODO: check client username contains space

    # check port value is integer
    try:
        int(sys.argv[1])
    except ValueError:
        print(f"Error: Unable to connect to port {sys.argv[1]}.", file=sys.stderr)
        exit(EXIT_CODES.PORT_CHECK_ERROR.value)

    # check port within ranges
    if int(sys.argv[1]) < 1024 or int(sys.argv[1]) > 65535:  # port number out of range
        print(f"Error: Unable to connect to port {sys.argv[1]}.", file=sys.stderr)
        exit(EXIT_CODES.PORT_CHECK_ERROR.value)

    return

def start_connection(port):
    # Check chatclient can connect to server on socket
    hostname = "localhost"
    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((hostname, port))
        return sock # return the created socket
    except Exception:
        print(f"Error: Unable to connect to port {port}.", file=sys.stderr)
        exit(EXIT_CODES.PORT_CHECK_ERROR.value)

def handle_stdin(sock):
    global quit, mute, mute_duration, file_path, sending
    while True: 
        try: 
            for line in stdin:
                commands = line.split(" ")

                if commands[0] == "/quit" or commands[0] == "/quit\n":
                    if len(commands) > 1: # extra arguments
                        print("[Server Message] Usage: /quit", file=sys.stdout)
                        sys.stdout.flush()
                    else:
                        quit = True
                        sock.send(line.encode())
                        sock.close()
                        sys.exit(0)
                elif commands[0] == "/list" or commands[0] == "/list\n":
                    if len(commands) > 1: # extra arguments
                        print("[Server Message] Usage: /list", file=sys.stdout)
                        sys.stdout.flush()
                    else: 
                        sock.send(line.encode()) # server will handle list command
                elif commands[0] == "/whisper" or commands[0] == "/whisper\n":
                    commands = line.split(maxsplit=2)
                    if len(commands) != 3: # too little/many arguments, unnecessary since maxsplit 2
                        print("[Server Message] Usage: /whisper receiver_client_username chat_message", file=sys.stdout, flush=True)
                    elif commands[1] == "" or commands[1] == " " or commands[2] == "" or commands[2] == " ": # any argument is empty space
                        print("[Server Message] Usage: /whisper receiver_client_username chat_message", file=sys.stdout, flush=True)
                    elif mute: 
                        print(f"[Server Message] You are still in mute for {mute_duration} seconds.", file=sys.stdout, flush=True)
                    else: 
                        sock.send(line.encode()) # server will handle whisper command
                elif commands[0] == "/send" or commands[0] == "/send\n":
                    commands = line.split(maxsplit=2)
                    if len(commands) != 3:
                        print("[Server Message] Usage: /send target_client_username file_path", file=sys.stdout, flush=True)
                    elif commands[1] == "" or commands[1] == " " or commands[2] == "" or commands[2] == " ":
                        print("[Server Message] Usage: /send target_client_username file_path", file=sys.stdout, flush=True)
                    elif not re.match(r'^[\x21-\x7E]*$', commands[1]) or not re.match(r'^[\x21-\x7E]*$', commands[2]):
                        print("[Server Message] Usage: /send target_client_username file_path", file=sys.stdout, flush=True)
                    elif mute: 
                        print(f"[Server Message] You are still in mute for {mute_duration} seconds.", file=sys.stdout, flush=True)
                    else:
                        file_path = commands[2].strip()
                        sock.send(line.encode())
                        sending = True

                        # data = sock.recv(BUFSIZE).decode().strip()
                        # if data == "[Server Message] Start transmisson.":
                elif commands[0] == "/switch":
                    if len(commands) != 2: # too little/many arguments
                        print("[Server Message] Usage: /switch channel_name", file=sys.stdout, flush=True)
                    elif commands[1] == "" or commands[1] == " ":
                        print("[Server Message] Usage: /switch channel_name", file=sys.stdout, flush=True)
                    else: 
                        sock.send(line.encode())
                elif commands[0] == "/switch\n": 
                    print("[Server Message] Usage: /switch channel_name", file=sys.stdout, flush=True) 
                else:
                    if mute: 
                        print(f"[Server Message] You are still in mute for {mute_duration} seconds.", file=sys.stdout, flush=True)
                    else:
                        sock.send(line.encode())
        except KeyboardInterrupt:
            sock.close()
            sys.exit(0)
            break

def handle_socket(sock, client_username):
    global quit, mute, mute_duration, client_doesnt_exist, file_path, sending

    while True: 
        try: 
            data = sock.recv(BUFSIZE).decode().strip()

            # if re.match(r'^\[Server Message\] ".*?" is not in the channel\.$', data) and sending == True:
            if re.match(r'^\[Server Message\] .+ is not in the channel\.$', data): 
                print(data, file=sys.stdout,flush=True)
                client_doesnt_exist = True # server gave error that client sending to doesn't exist
                continue

            if data == "[Server Message] Start transmission." and sending == True:
                try:
                    with open(file_path, "rb") as file:

                        if client_doesnt_exist: # don't send 
                            continue
                        else: # send
                            file_data = file.read()

                            # Send file size
                            file_size = len(file_data)
                            message = f"[FileSize] {file_size}"
                            sock.sendall(message.encode())

                            # Send file data 
                            sock.sendall(file_data)
                            # sending = False
                            # file_path = None
                except FileNotFoundError:
                    print(f"[Server Message] \"{file_path}\" does not exist.", file=sys.stdout, flush=True)
                    
                sending = False
                file_path = None
                client_doesnt_exist = False
                continue # stop with sending 

            client_doesnt_exist = False
            sending = False
            file_path = None

            if re.match(r"^\[Server Message\] FileSize \S+ \d+$", data): # server wants to send file
                data = data.strip()
                commands = data.split(" ")
                file_size = int(commands[4])
                basename = commands[3]
    	
                message = "[Client Message] Ready"
                sock.sendall(message.encode())

                file_data = b""
                while len(file_data) < file_size: 
                    current = sock.recv(min(BUFSIZE, file_size - len(file_data)))
                    if not current:
                        # failed
                        message = "[Client Message] File Transfer Failed"
                        sock.sendall(message.encode())
                        continue
                    file_data += current

                if not len(file_data) == file_size: 
                    message = "[Client Message] File Transfer Failed"
                    sock.sendall(message.encode())
                else: 
                    message = "[Client Message] Received"
                    sock.sendall(message.encode())

                    with open(basename, "wb") as f:
                        f.write(file_data)

                continue
            
            afk_message = rf'^\[Server Message\] {re.escape(client_username)} went AFK in channel ".*?"\.$'
            if re.match(afk_message, data):
                print(data, file=sys.stdout, flush=True)
                os._exit(0)

            empty_kick_message = "[Server Message] You are removed from the channel."
            if data == empty_kick_message:
                print(data, file=sys.stdout,flush=True)
                os._exit(0)

            if not data:
                if not quit:
                    print("Error: server connection closed.", file=sys.stderr, flush=True)
                    os._exit(EXIT_CODES.DISCONNECT_ERROR.value)
                else:
                    os._exit(0)

            mute_message = r'^\[Server Message\] You have been muted for .*? seconds\.$'
            if re.match(mute_message, data):
                print(data, file=sys.stdout, flush=True)
                # Extract duration
                match = re.search(r"(\b\d+)", data)
                duration = int(match.group(1))
                handle_mute(duration)
            else:   
                print(data, file=sys.stdout, flush=True)
        except KeyboardInterrupt:
            sock.close()
            sys.exit(0)
            break

def handle_mute(duration):
    global mute, mute_duration, mute_counter
    
    mute = True
    mute_duration = duration
    mute_counter += 1 # increment counter

    def unmute(current_duration, current_counter):
        global mute, mute_duration, mute_counter
        time.sleep(current_duration)
        if current_counter != mute_counter: # if another mute sent, don't change the mute variable until that mute is over
            pass
        else:
            mute = False

    current_counter = mute_counter
    unmute_thread = Thread(target=unmute, args=(duration, current_counter))
    unmute_thread.daemon = True
    unmute_thread.start()

def main():

    usage_checking()
    # check port is integer here while converting
    port = None
    try:
        port = int(sys.argv[1])
    except:
        print(f"Error: Unable to connect to port {port}.", file=sys.stderr)
        exit(EXIT_CODES.PORT_CHECK_ERROR.value)

    client_username = sys.argv[2]

    sock = start_connection(port) # returns connected socket to send stuff on
    sock.send(client_username.encode()) # send username to server
    response = sock.recv(BUFSIZE).decode().strip() # server response - either username already exists or "welcome to chatclient"... - see spec

    # flush either message (welcome message or username error message) to stdout
    print(response, file=sys.stdout, flush=True)
    
    # if got username error, also exit program status 2
    # TODO: check this message is ok
    username_error_message = rf"^\[Server Message\] Channel \".*\" already has user {client_username}\.$"
    if re.match(username_error_message, response):
        exit(EXIT_CODES.DUPLICATE_USERNAME_ERROR.value)

    response = sock.recv(BUFSIZE).decode().strip() # server response - either you have joined channel or in queue
    print(response, file=sys.stdout)
    sys.stdout.flush()

    # Ready for communication
    # Open 2 threads
    # - one for reading from stdin and sending data
    # - one for reading from the socket and receiving data from server/channel

    # create thread to read from stdin
    stdin_thread = Thread(target=handle_stdin, args=(sock, ))
    stdin_thread.daemon = True
    stdin_thread.start()

    # create thread to read from network socket from server
    socket_thread = Thread(target=handle_socket, args=(sock, client_username))
    socket_thread.daemon = True
    socket_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sock.close()
        sys.exit(0)


    try:
        stdin_thread.join()
        socket_thread.join()
    except KeyboardInterrupt:
        sock.close()
        sys.exit(0) # what exit code is it? 8? 

    sock.close() # somewhere close socket once connection terminated?

if __name__ == "__main__":
    main()
