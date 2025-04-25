import sys
from socket import *
from sys import stdout, stdin, argv, exit

BUFSIZE = 1024


def usage_checking(arr):
    if len(sys.argv) < 3 or len(sys.argv) > 3:  # Not enough/too many arguments
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(3)

    if sys.argv[1] == "" or sys.argv[2] == "":  # empty strings
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(3)

    # TODO: NOT SURE IF THIS SHOULD BE DONE HERE?? SINCE PORT NUUMBER NOT CHECKED AS INT YET
    if int(sys.argv[1]) < 1024 or int(sys.argv[1]) > 65535:  # port number out of range
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(3)

    return


def start_connection(port):
    # Check port number is integer
    if not port.isdigit():
        print(f"Error: Unable to connect to port {port}.\n", file=sys.stderr)
        exit(7)

    # Check chatclient can connect to server on socket
    hostname = "localhost"
    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((hostname, port))
        return sock # return the created socket
    except Exception:
        print(f"Error: Unable to connect to port {port}.\n", file=sys.stderr)
        exit(7)

def main():
    usage_checking(sys.argv)
    port = int(sys.argv[1])
    client_username = sys.argv[2]
    sock = start_connection(port) # returns connected socket to send stuff on
    sock.send(client_username.encode()) # send username to server
    data = sock.recv(BUFSIZE) # receive server response to username


if __name__ == "__main__":
    main()
