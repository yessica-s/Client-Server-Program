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
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR)

    if sys.argv[1] == "" or sys.argv[2] == "":  # empty strings
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR)

    # TODO: NOT SURE IF THIS SHOULD BE DONE HERE?? SINCE PORT NUUMBER NOT CHECKED AS INT YET
    if int(sys.argv[1]) < 1024 or int(sys.argv[1]) > 65535:  # port number out of range
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(EXIT_CODES.USAGE_ERROR)

    return

def start_connection(port):
    # Check port number is integer
    if not port.isdigit():
        print(f"Error: Unable to connect to port {port}.\n", file=sys.stderr)
        exit(EXIT_CODES.PORT_CHECK_ERROR)

    # Check chatclient can connect to server on socket
    hostname = "localhost"
    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((hostname, port))
        return sock # return the created socket
    except Exception:
        print(f"Error: Unable to connect to port {port}.\n", file=sys.stderr)
        exit(EXIT_CODES.PORT_CHECK_ERROR)

def handle_stdin(sock):
    while True: 
        for line in stdin:
            sock.send(line.encode())
            data = sock.recv(BUFSIZE)
            if not data:
                    break
            stdout.buffer.write(data)
            stdout.flush()

def handle_socket(sock):
    pass

def main():
    usage_checking()
    port = int(sys.argv[1])
    client_username = sys.argv[2]

    sock = start_connection(port) # returns connected socket to send stuff on
    sock.send(client_username.encode()) # send username to server
    response = sock.recv(BUFSIZE).decode().strip() # server response - either username already exists or "welcome to chatclient"... - see spec

    # flush either message (welcome message or username error message) to stdout
    print(response, file=sys.stdout)
    sys.stdout.flush()
    
    # if got username error, also exit program status 2
    username_error_message = rf"^\[Server Message\] Channel \".*\" already has user {client_username}\.\n$"
    if re.match(username_error_message, response):
        exit(EXIT_CODES.DUPLICATE_USERNAME_ERROR)

    response = sock.recv(BUFSIZE).decode().strip() # server response - either joined channel or in queue
    print(response, file=sys.stdout)
    sys.stdout.flush()

    # Ready for communication
    # Open 2 threads
    # - one for reading from stdin and sending data
    # - one for reading from the socket and receiving data from server/channel
    # TODO: do the same for server, per client, one thread to read, one threat to write

    # create thread to read from stdin
    stdin_thread = Thread(target=handle_stdin, args=(sock, ))
    stdin_thread.start()

    # create thread to read from network socket from server
    socket_thread = Thread(target=handle_socket, args=(sock, ))
    socket_thread.start()  


if __name__ == "__main__":
    main()
