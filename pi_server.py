import socket

HOST ='' # just 0.0.0.0 - all avail channels ie lan, eth, etc. as opposed to just picking one channel
PORT = 8080 # dev port

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT)) # says socket listens to specified channels, on given port
    s.listen(1) # starts listening for incoming conns, 1 is amount of unaccepted connections allowed in queue

    print(f"Serving on port: {PORT}")

    while True:
        conn, addr = s.accept() # .accept() blocks (halts) until someone connects, returning new conn object for this
        # ... connection and the ip address of the connection

        with conn:
            print(f"Connected by address: {addr}")

            raw_request = conn.recv(1024) # receives HTTP request bytes, max 1024

            request = raw_request.decode()
            print(f"HTTP request decoded: {request}")

            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-type: text/html\r\n"
                "Connection: close\r\n"
                "\r\n"
                "<html><body><h1>Hello from balls<h1><body><html>\r\n"
            )
            conn.sendall(response.encode()) # converts response to bytes and sends to client