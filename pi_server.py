import os
import socket
import pandas as pd
import time
import mimetypes

HOST ='' # just 0.0.0.0 - all avail channels ie lan, eth, etc. as opposed to just picking one channel
PORT = 8080 # dev port
LEADERBOARD = []

# caching name to use when finish blowing
PENDING_NAME = {}  # {"name": str, "timestamp": float}
MOST_RECENT = {}


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

def serve_static_file(path):
    """Serve static files from the static/ directory"""
    # Remove leading slash and ensure it's in static directory
    if path.startswith('/static/'):
        file_path = path[1:]  # Remove leading slash
    else:
        file_path = f"static{path}"
    
    # Security check - prevent directory traversal
    if '..' in file_path or not file_path.startswith('static/'):
        return None
    
    if not os.path.exists(file_path):
        return None
    
    try:
        with open(file_path, 'rb') as f:
            content = f.read()
        
        # Get MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            if file_path.endswith('.js'):
                mime_type = 'application/javascript'
            elif file_path.endswith('.css'):
                mime_type = 'text/css'
            elif file_path.endswith('.html'):
                mime_type = 'text/html'
            else:
                mime_type = 'application/octet-stream'
        
        return content, mime_type
    except Exception:
        return None


def generate_session_id():
    """Generate a simple session ID"""
    return str(int(time.time() * 1000))[-8:]  # Last 8 digits of timestamp


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
                # this is just for testing
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

            elif method == "POST" and path == "/cache-name":
                # Cache user's name for breathalyzer workflow
                body = lines[-1]
                print(f"POST body: {body}")

                try:
                    params = dict(p.split("=") for p in body.split("&"))
                    name = params.get("name", "").strip().replace(",", "")
                    
                    if not name:
                        response = (
                            "HTTP/1.1 400 Bad Request\r\n"
                            "Content-Type: text/plain\r\n"
                            "Connection: close\r\n"
                            "\r\n"
                            "Name is required\r\n"
                        )
                    else:
                        # check if someone else is already pending
                        if PENDING_NAME != {}:
                            response = (
                                "HTTP/1.1 201 BUSY\r\n"
                                "Content-Type: text/plain\r\n"
                                "Connection: close\r\n"
                                "\r\n"
                                f"Another user is already pending\r\n"
                            )
                        
                        else:
                            # Generate session ID and cache name
                            PENDING_NAME = {
                                "name": name,
                                "timestamp": time.time()
                            }

                            response = (
                                "HTTP/1.1 200 OK\r\n"
                                "Content-Type: text/plain\r\n"
                                "Connection: close\r\n"
                                "\r\n"
                                f"Success initializing session\r\n"
                            )

                except Exception as e:
                    response = (
                        "HTTP/1.1 400 Error\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error: {e}\r\n"
                    )

            elif method == "POST" and path == "/submit-bac":
                # Submit BAC reading and match with cached name
                body = lines[-1]
                print(f"POST body: {body}")

                try:
                    params = dict(p.split("=") for p in body.split("&"))
                    bac = float(params.get("bac", "0"))
                    timest = time.time()
                    
                    # Find cached name for this session
                    write_data = {
                        "name": PENDING_NAME.get("name"),
                        "bac": bac,
                        "timestamp": timest
                    }

                    # setting most recent
                    MOST_RECENT = {
                        "name": PENDING_NAME.get("name"),
                        "bac": bac,
                        "timestamp": timest
                    }

                    # clear from pending
                    PENDING_NAME = {}
                        
                    # Save to CSV
                    og_df = load_csv()

                    # insert row at correct place
                    bac_list = og_df["bac"].tolist() if "bac" in og_df else []
                    insert_index = bin_search(bac_list, bac)
                    MOST_RECENT["rank"] = insert_index

                    new_row = write_data
                    top = og_df.iloc[:insert_index]
                    bottom = og_df.iloc[insert_index:]
                    og_df = pd.concat([top, pd.DataFrame([new_row]), bottom]).reset_index(drop=True)

                    og_df.to_csv("../namesBac.csv", index=False)

                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Success: {name} - {bac:.3f}\r\n"
                    )

                except Exception as e:
                    response = (
                        "HTTP/1.1 400 Error\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error: {e}\r\n"
                    )


            if method == "GET" and path == "/":
                # Serve the main index.html file
                static_result = serve_static_file("/index.html")
                if static_result:
                    content, mime_type = static_result
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        f"Content-Type: {mime_type}\r\n"
                        f"Content-Length: {len(content)}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    ).encode() + content
                else:
                    response = (
                        "HTTP/1.1 404 Not Found\r\n"
                        "Content-Type: text/html\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        "<html><body><h1>404 Not Found</h1></body></html>\r\n"
                    )

            elif method == "GET" and path.startswith("/static/"):
                # Serve static files (CSS, JS, images, etc.)
                static_result = serve_static_file(path)
                if static_result:
                    content, mime_type = static_result
                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        f"Content-Type: {mime_type}\r\n"
                        f"Content-Length: {len(content)}\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                    ).encode() + content
                else:
                    response = (
                        "HTTP/1.1 404 Not Found\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        "File not found\r\n"
                    )

            elif method == "GET" and path == "/leaderboard":
                try:
                    og_df = load_csv()

                    if "timestamp" in og_df:
                        og_df["time"] = pd.to_datetime(og_df["timestamp"], unit="s")

                    html_table = og_df[["name", "bac", "time"]].to_html(
                        index=False, float_format="%.3f"
                    )

                    response = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/html\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"{html_table}"
                    )

                except Exception as e:
                    response = (
                        "HTTP/1.1 500 Internal Server Error\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error displaying leaderboard: {e}\r\n"
                    )

            elif method == "GET" and path == "/recent":
                # Get most recent reading
                try:
                    if MOST_RECENT:
                        response = (
                            "HTTP/1.1 200 OK\r\n"
                            "Content-Type: application/json\r\n"
                            "Connection: close\r\n"
                            "\r\n"
                            f'{{"name": "{MOST_RECENT.get("name", "")}", "bac": {MOST_RECENT.get("bac", 0)}, "timestamp": {MOST_RECENT.get("timestamp", 0)}, "rank": {MOST_RECENT.get("rank", 0)}}}\r\n'
                        )
                    else:
                        response = (
                            "HTTP/1.1 200 OK\r\n"
                            "Content-Type: application/json\r\n"
                            "Connection: close\r\n"
                            "\r\n"
                            '{"name": "", "bac": 0, "timestamp": 0, "rank": 0}\r\n'
                        )
                except Exception as e:
                    response = (
                        "HTTP/1.1 500 Internal Server Error\r\n"
                        "Content-Type: text/plain\r\n"
                        "Connection: close\r\n"
                        "\r\n"
                        f"Error: {e}\r\n"
                    )

            elif method == "GET" and path == "/status":
                try:
                    og_df = load_csv()

                    if og_df.empty:
                        msg = "No entries yet."
                    else:
                        latest_ts = MOST_RECENT.get("timestamp") if MOST_RECENT.get("timestamp") else (og_df["timestamp"].max())
                        elapsed = int(time.time()) - latest_ts

                        if elapsed <= 900:  # 15 minutes = 900 seconds
                            msg = f"Last blow was {elapsed // 60} min ago → OK"
                        else:
                            msg = f"Last blow was {elapsed // 60} min ago → TOO LONG"
                    if PENDING_NAME != {}:
                        msg = "BUSY. Someone is already in the process"

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

            if 'response' not in locals() or response is None:
                response = (
                    "HTTP/1.1 404 Not Found\r\n"
                    "Content-Type: text/html\r\n"
                    "Connection: close\r\n"
                    "\r\n"
                    "<html><body><h1>404 Not Found</h1></body></html>\r\n"
                )

            # Send response - handle both string and bytes responses
            if isinstance(response, str):
                conn.sendall(response.encode())
            else:
                conn.sendall(response)