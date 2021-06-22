#!/usr/bin/env python3.7.6
import time
import socket
import datetime
import sys

rtts = []

for pings in range(15):
    # create a socket
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # set timeout to 600ms
    client_socket.settimeout(0.6)
    # create a byte message
    message = f"PING {3331+pings} {datetime.datetime.now()}".encode()
    # set address to localhost, on port 5000
    addr = (str(sys.argv[-2]), int(sys.argv[-1]))
    
    # get start time and send message
    start = time.time()
    client_socket.sendto(message, addr)
    try:
        # receive message from server
        data, server = client_socket.recvfrom(1024)
        # after received message, get the end time
        end = time.time()
        # find the rtt
        rtt = end - start
        rtt = int(rtt*1000)
        rtts.append(rtt)
        print(f"ping to 127.0.0.1, seq = {pings}, rtt = {rtt}ms")
    except socket.timeout:
        # if timeout, print timeout
        print(f"ping to 127.0.0.1, seq = {pings}, rtt = timeout")
if rtts:
    print(f"minimum rtt = {min(rtts)}ms, average rtt = {int(sum(rtts)/len(rtts))}ms, maximum rtt = {max(rtts)}ms")
else:
    print("minimum rtt = none, average rtt = none, maximum rtt = none")