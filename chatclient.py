import sys
from socket import *
from sys import stdout, stdin, argv, exit
import re
from enum import Enum
from threading import Thread

BUFSIZE = 1024

class EXIT_CODES(Enum):
    USAGE_ERROR = 3
    PORT_CHECK_ERROR = 7
    DUPLICATE_USERNAME_ERROR = 2

def usage_checking():
    if len(sys.argv) < 3 or len(sys.argv) > 3:  # Not enough/too many arguments
        print("Usage: chatclient port_number client_username", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    if sys.argv[1] == "" or sys.argv[2] == "":  # empty strings
        print("Usage: chatclient port_number client_username", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

    # TODO: NOT SURE IF THIS SHOULD BE DONE HERE?? SINCE PORT NUUMBER NOT CHECKED AS INT YET
    if int(sys.argv[1]) < 1024 or int(sys.argv[1]) > 65535:  # port number out of range
        print("Usage: chatclient port_number client_username", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR.value)

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
    while True: 
        for line in stdin:
            sock.send(line.encode())
            data = sock.recv(BUFSIZE)
            if not data:
                break
            # stdout.buffer.write(data)
            # stdout.flush()
            print(data.decode().strip(), file=sys.stdout)
            sys.stdout.flush()

def handle_socket(sock):
    while True: 
        print("here")
        data = sock.recv(BUFSIZE)
        # afk_message = rf"[Server Message] {client_username} went AFK in channel \".*\"."
        # if re.match(afk_message, data):
        #     exit(8) # AFK, clean this up
        if not data:
            exit(8) # AFK, clean this up 
        print(data.decode().strip(), file=sys.stdout)
        sys.stdout.flush()

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
    print(response, file=sys.stdout)
    sys.stdout.flush()
    
    # if got username error, also exit program status 2
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
    stdin_thread.start()

    # create thread to read from network socket from server
    socket_thread = Thread(target=handle_socket, args=(sock))
    socket_thread.start()  

    # wait for threads to finish
    stdin_thread.join()
    socket_thread.join()

    sock.close() # somewhere close socket once connection terminated?

if __name__ == "__main__":
    main()
