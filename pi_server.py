import os
import socket
import pandas as pd

HOST ='' # just 0.0.0.0 - all avail channels ie lan, eth, etc. as opposed to just picking one channel
PORT = 8080 # dev port
LEADERBOARD = []


def bin_search(lst, val):
    """Binary search for descending list; return insertion index."""
    left, right = 0, len(lst) - 1
    while left <= right:
        mid = (left + right) // 2
        if lst[mid] == val:
            return mid
        elif lst[mid] > val:
            left = mid + 1   # go right because values decrease
        else:
            right = mid - 1
    return left


def load_csv(path="../namesBac.csv"):
    if not os.path.exists(path):
        return pd.DataFrame(columns=["name", "bac"])
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=["name", "bac"])


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT)) # says socket listens to specified channels, on given port
    s.listen(1) # starts listening for incoming conns, 1 is amount of unaccepted connections allowed in queue

    print(f"Serving on port: {PORT}")

    while True:
        conn, addr = s.accept() # .accept() blocks (halts) until someone connects, returning new conn object for this
        # ... connection and the ip address of the connection

        with conn:
            print(f"Connected by address: {addr}")

            raw_request = conn.recv(1024) # receives HTTP request in BYTES, max 1024

            request = raw_request.decode()
            print(f"HTTP request decoded: {request}")

            lines = request.split("\r\n")
            request_line = lines[0]
            method, path, version = request_line.split(" ") #ie GET / HTTP/1.1
            print(f"Method: {method}, Path: {path}")

            if method == "POST" and path == "/submit":
                # "name=Jack&score=0.09"
                body = lines[-1] #it's the last line
                print(f"POST body: {body}")

                try:
                    # extracting name and bac
                    name = body.split("&")[0].split("=")[1].strip().replace(",", "")
                    bac = float(body.split("&")[1].split("=")[1])

                    # write out to csv, from path ~/breath/ to ~/
                    # just figure out correct place for entry each write
                    og_df = load_csv()

                    # now binary search for entry position
                    bac_list = og_df["bac"].tolist()
                    insert_index = bin_search(bac_list, bac)

                    # new row inserting
                    new_row = {"name": name, "bac": bac}
                    top = og_df.iloc[:insert_index]
                    bottom = og_df.iloc[insert_index:]
                    og_df = pd.concat([top, pd.DataFrame([new_row]), bottom]).reset_index(drop=True)

                    og_df.to_csv("../namesBac.csv", index=False)
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        "Success\r\n"
                    )

                except Exception as e:
                    response = (
                        "HTTP/1.1 400 Error\r\n"
                        "Content-type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error: {e}\r\n"
                    )

            if method == "GET" and path == "/leaderboard":
                try:
                    # load the leaderboard
                    og_df = load_csv()

                    # convert DataFrame into an HTML table
                    html_table = og_df.to_html(index=False, float_format="%.3f")

                    # wrap in simple HTML page
                    html_page = f"""
                        <html>
                        <head>
                            <title>Breathalyzer Leaderboard</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; background: #f9f9f9; }}
                                h1 {{ text-align: center; }}
                                table {{ margin: auto; border-collapse: collapse; }}
                                th, td {{ border: 1px solid #ccc; padding: 8px 12px; }}
                                th {{ background: #eee; }}
                            </style>
                        </head>
                        <body>
                            <h1>Leaderboard</h1>
                            {html_table}
                        </body>
                        </html>
                        """

                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/html\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"{html_page}"
                    )

                except Exception as e:
                    response = (
                        "HTTP/1.1 500 Internal Server Error\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error displaying leaderboard: {e}\r\n"
                    )

            if response is None:
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    "<html><body><h1>404 Not Found</h1></body></html>\r\n"
                )

            conn.sendall(response.encode()) # converts response to bytes and sends to client