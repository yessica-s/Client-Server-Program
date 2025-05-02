import sys, os
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

def handle_socket(sock, client_username):
    while True: 
        data = sock.recv(BUFSIZE).decode().strip()

        afk_message = rf'^\[Server Message\] {re.escape(client_username)} went AFK in channel ".*?"\.$'
        if re.match(afk_message, data):
            print(data, file=sys.stdout)
            os._exit(EXIT_CODES.DISCONNECT_ERROR.value) # AFK, clean this up

        if not data:
            print("Error: server connection closed.")
            os._exit(EXIT_CODES.DISCONNECT_ERROR.value) # AFK, clean this up
            
        print(data, file=sys.stdout)
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
    stdin_thread.start()

    # create thread to read from network socket from server
    socket_thread = Thread(target=handle_socket, args=(sock, client_username))
    socket_thread.start()  

    # wait for threads to finish
    stdin_thread.join()
    socket_thread.join()

    sock.close() # somewhere close socket once connection terminated?

if __name__ == "__main__":
    main()
