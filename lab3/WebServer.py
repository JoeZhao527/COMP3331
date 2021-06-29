#!/usr/bin/env python3

import sys
from socket import *

def open_server(port):
    # create a server in localhost, listen at "port"
    server = socket(AF_INET, SOCK_STREAM)
    server.bind(('localhost', port))
    server.listen(1)
    print(f'Server is listening on http://127.0.0.1:{port}/index.html')

    # the server listens in a loop, waiting for the next request from the browser
    while True:
        conn, addr = server.accept()
        respond_request(conn)

def respond_request(conn):
    sentence = conn.recv(1024)
    try:
        # parse the request to determine the specific file being requested
        file_name = sentence.split()[1][1:]

        # if the file is found, load the page, and send back the file as request
        file = open(file_name, 'rb').read()

        conn.send(b'HTTP/1.1 200 OK\r\n')

        if 'png' in str(file_name):
            conn.send(b'Content-Type: image/png \r\n\r\n')
        elif 'html' in str(file_name):
            conn.send(b'Content-Type: text/html \r\n\r\n')

        conn.send(file)
        conn.close()

    except IOError:
        # otherwise the page is not found, returns 404 error
        conn.send(b'HTTP/1.1 404 Not Found\r\n')
        conn.send(b'Content-Type: text/html \r\n\r\n')
        conn.send(b'<html><h1>404 Page Not Found</h1><p>The page that you requested is not exist</p></html>')
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2 :
        port = 8080
    else:
        port = int(sys.argv[1])
    open_server(port)