import sys
from socket import *
from sys import stdout,stdin,argv,exit

class Channel: 
    def __init__(self, name, port, capacity):
        self.name = name
        self.port = port
        self.capacity = capacity
        # self.clients = [] # connected clients
        # self.queue = [] # clients waiting to join

class Server: 
    channels = []
    channel_names = [] 
    pass


def usage_checking(arr): 
    config_file = None
    afk_time = None

    if len(sys.argv) not in (2,3): # too little/ too many arguments
        print("Usage: chatserver [afk_time] config_file", file=sys.stderr)
        exit(4)

    config_file = sys.argv[1] # default as only argument if afk_time not present

    if len(sys.argv) == 3: # afk_time argument present, need to check btwn 1 and 1000 inclusive
        if not sys.argv[1].isdigit(): 
            print("Usage: chatserver [afk_time] config_file", file=sys.stderr)
            exit(4)
        
        afk_time = int(sys.argv[1])
        config_file = sys.argv[2] # if afk_time argument present, change to second argument

        if afk_time < 1 or afk_time > 1000: # out of range
            print("Usage: chatserver [afk_time] config_file", file=sys.stderr)
            exit(4)

    # attempt to open the configuration file
    try:
        file = open(config_file)
        file.close()
    except FileNotFoundError:
        print("Error: Invalid configuration file.", file=sys.stderr)
        exit(5)

    check_config_file(config_file)
    return config_file, afk_time

def check_config_file(config_file):
    with open(config_file, 'r') as file: 
        while True:
            line = file.readline()

            if not line: # break when EOF reached
                break

            line = line.strip() # remove leading or trailing whitespace
            channel = line.split(" ")

            if not len(channel) == 4: # too little/many arguments
                print("Error: Invalid configuration file.", file=sys.stderr)
                exit(5)
            
            channel_port = channel[2]
            channel_capacity = channel[3]

            if not channel_port.isdigit(): # check port is integer
                print("Error: Invalid configuration file.", file=sys.stderr)
                exit(5)

            channel_port = int(channel[2]) # convert to int after checking

            if not (1024 <= channel_port <= 65535): # port out of range
                print("Error: Invalid configuration file.", file=sys.stderr)
                exit(5)

            if not channel_capacity.isdigit(): # check capacity is integer
                print("Error: Invalid configuration file.", file=sys.stderr)
                exit(5)

            channel_capacity = int(channel[3]) # convert to int after checking

            if not (1 <= channel_capacity <= 8): # port out of range
                print("Error: Invalid configuration file.", file=sys.stderr)
                exit(5)

            
    


         




                   
def main():
    config_file, afk_time = usage_checking(sys.argv)


if __name__ == "__main__":
    main()