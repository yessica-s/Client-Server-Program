import sys
from socket import *
from sys import stdout, stdin, argv, exit


def usage_checking(arr):
    if len(sys.argv) < 3 or len(sys.argv) > 3:  # Not enough/too many arguments
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(3)

    if sys.argv[1] == "" or sys.argv[2] == "":  # empty strings
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(3)

    # TODO: NOT SURE IF THIS SHOULD BE DONE HERE?? SINCE PORT NUUMBER NOT CHECKED AS INT YET
    if sys.argv[1] < 1024 or sys.argv[1] > 65535:  # port number out of range
        print("Usage: chatclient port_number client_username\n", file=sys.stderr)
        exit(3)

    return

def check_port(port):
    # Check port number is integer
    if not port.isdigit():
        print(f"Error: Unable to connect to port {port}.\n", file=sys.stderr)
        exit(7)

    # Check chatclient can connect to server on socket
    hostname = "localhost"
    sock = socket(AF_INET, SOCK_STREAM)
    try:
        sock.connect((hostname, port))
    except Exception:
        print(f"Error: Unable to connect to port {port}.\n", file=sys.stderr)
        exit(7)


def check_username(client):
    # TODO: NEED TO IMPLEMENT BASED ON SERVER PROTOCOL
    pass

def main():
    usage_checking(sys.argv)
    port = sys.argv[1]
    client = sys.argv[2]
    check_port(port)
    check_username(client)


if __name__ == "__main__":
    main()
