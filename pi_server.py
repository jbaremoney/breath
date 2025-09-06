import os
import socket
import pandas as pd
import time

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
                # Example body: "name=Jack&score=0.09&timestamp=1736210521"
                body = lines[-1]
                print(f"POST body: {body}")

                try:
                    params = dict(p.split("=") for p in body.split("&"))
                    name = params.get("name", "").strip().replace(",", "")
                    bac = float(params.get("score", "0"))

                    # use provided timestamp if valid, else current unix time
                    ts = params.get("timestamp")
                    if ts and ts.isdigit():
                        timestamp = int(ts)
                    else:
                        timestamp = int(time.time())

                    # load leaderboard
                    og_df = load_csv()

                    # insert row at correct place
                    bac_list = og_df["bac"].tolist() if "bac" in og_df else []
                    insert_index = bin_search(bac_list, bac)

                    new_row = {"name": name, "bac": bac, "timestamp": timestamp}
                    top = og_df.iloc[:insert_index]
                    bottom = og_df.iloc[insert_index:]
                    og_df = pd.concat([top, pd.DataFrame([new_row]), bottom]).reset_index(drop=True)

                    og_df.to_csv("../namesBac.csv", index=False)

                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        "Success\r\n"
                    )

                except Exception as e:
                    response = (
                        "HTTP/1.1 400 Error\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error: {e}\r\n"
                    )

            if method == "GET" and (path == "/leaderboard" or path == "/"):
                try:
                    og_df = load_csv()

                    if "timestamp" in og_df:
                        og_df["time"] = pd.to_datetime(og_df["timestamp"], unit="s")

                    html_table = og_df[["name", "bac", "time"]].to_html(
                        index=False, float_format="%.3f"
                    )

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

            elif method == "GET" and path == "/status":
                try:
                    og_df = load_csv()

                    if og_df.empty:
                        msg = "No entries yet."
                    else:
                        latest_ts = int(og_df["timestamp"].max())
                        elapsed = int(time.time()) - latest_ts

                        if elapsed <= 900:  # 15 minutes = 900 seconds
                            msg = f"Last blow was {elapsed // 60} min ago → OK"
                        else:
                            msg = f"Last blow was {elapsed // 60} min ago → TOO LONG"

                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"{msg}\r\n"
                    )

                except Exception as e:
                    response = (
                        "HTTP/1.1 500 Internal Server Error\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error checking status: {e}\r\n"
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