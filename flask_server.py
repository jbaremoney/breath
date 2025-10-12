from flask import Flask, request, jsonify, send_from_directory, render_template_string
import pandas as pd
import time
import os
import mimetypes

app = Flask(__name__)

# Global variables (consider using a database or session storage for production)
PENDING_NAME = {}
MOST_RECENT = {}
READY = False

# Helper functions (you'll need to include these from your original code)
def load_csv():
    """Load the CSV file, create if doesn't exist"""
    try:
        return pd.read_csv("../namesBac.csv")
    except FileNotFoundError:
        # Create empty DataFrame with required columns
        df = pd.DataFrame(columns=["name", "bac", "timestamp"])
        df.to_csv("../namesBac.csv", index=False)
        return df


def bin_search(arr, target):
    """Binary search to find insertion point for maintaining sorted order"""
    left, right = 0, len(arr)
    while left < right:
        mid = (left + right) // 2
        if arr[mid] > target:  # Assuming descending order (highest BAC first)
            left = mid + 1
        else:
            right = mid
    return left


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


@app.route('/')
def index():
    """Serve the main index.html file"""
    static_result = serve_static_file("/index.html")
    if static_result:
        content, mime_type = static_result
        return content, 200, {'Content-Type': mime_type}
    else:
        return "<html><body><h1>404 Not Found</h1></body></html>", 404


@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    static_result = serve_static_file(f"/static/{filename}")
    if static_result:
        content, mime_type = static_result
        return content, 200, {'Content-Type': mime_type}
    else:
        return "File not found", 404


@app.route('/cache-name', methods=['POST'])
def cache_name():
    """Cache user's name for breathalyzer workflow, ready the module"""
    global PENDING_NAME, READY

    try:
        name = request.form.get('name', '').strip().replace(',', '')

        if not name:
            return "Name is required", 400

        # Check if someone else is already pending
        if PENDING_NAME != {}:
            return "Another user is already pending", 201  # Using 201 as "BUSY" status

        # Generate session and cache name
        PENDING_NAME = {
            "name": name,
            "timestamp": time.time()
        }

        READY = True

        return "Success initializing session", 200



    except Exception as e:
        return f"Error: {e}", 400


@app.route('/submit-bac', methods=['POST'])
def submit_bac():
    """Submit BAC reading and match with cached name"""
    global PENDING_NAME, MOST_RECENT, READY

    print("BAC submit called")

    try:
        bac = float(request.form.get('bac', '0'))
        timest = time.time()

        # Get cached name
        cached_name = PENDING_NAME.get("name")

        write_data = {
            "name": cached_name,
            "bac": bac,
            "timestamp": timest
        }

        # Set most recent
        MOST_RECENT = {
            "name": cached_name,
            "bac": bac,
            "timestamp": timest
        }

        # Clear from pending
        PENDING_NAME = {}

        # Save to CSV
        og_df = load_csv()

        # Insert row at correct place
        bac_list = og_df["bac"].tolist() if "bac" in og_df else []
        insert_index = bin_search(bac_list, bac)
        MOST_RECENT["rank"] = insert_index

        new_row = write_data
        top = og_df.iloc[:insert_index]
        bottom = og_df.iloc[insert_index:]
        og_df = pd.concat([top, pd.DataFrame([new_row]), bottom]).reset_index(drop=True)

        og_df.to_csv("../namesBac.csv", index=False)
        READY = False

        return f"Success: {cached_name} - {bac:.3f}", 200

    except Exception as e:
        print("ERROR submitting BAC")
        return f"Error: {e}", 400


@app.route('/leaderboard')
def leaderboard():
    """Display leaderboard as HTML table"""
    try:
        og_df = load_csv()

        if "timestamp" in og_df:
            og_df["time"] = pd.to_datetime(og_df["timestamp"], unit="s")

        html_table = og_df[["name", "bac", "time"]].to_html(
            index=False, float_format="%.3f"
        )

        return html_table, 200, {'Content-Type': 'text/html'}

    except Exception as e:
        return f"Error displaying leaderboard: {e}", 500


@app.route('/recent')
def recent():
    """Get most recent reading as JSON"""
    try:
        if MOST_RECENT:
            return jsonify({
                "name": MOST_RECENT.get("name", ""),
                "bac": MOST_RECENT.get("bac", 0),
                "timestamp": MOST_RECENT.get("timestamp", 0),
                "rank": MOST_RECENT.get("rank", 0)
            })
        else:
            return jsonify({
                "name": "",
                "bac": 0,
                "timestamp": 0,
                "rank": 0
            })
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/blow-status')
def blow_status():
    """called by sparkfun to see if it's time to blow"""
    if READY:
        response = "READY"

    else:
        response = "WAIT"

    return response


@app.route('/status')
def status():
    """Check system status"""
    try:
        og_df = load_csv()

        if og_df.empty:
            msg = "No entries yet."
        else:
            latest_ts = MOST_RECENT.get("timestamp") if MOST_RECENT.get("timestamp") else (og_df["timestamp"].max())
            elapsed = int(time.time()) - latest_ts

            if elapsed <= 900:  # 15 minutes = 900 seconds
                msg = f"Last blow was {elapsed // 60} min ago → WAIT"
                print(msg)
            else:
                msg = f"Last blow was {elapsed // 60} min ago → READY"
                print(msg)

        if PENDING_NAME != {}:
            msg = "BUSY. Someone is already in the process"

        return msg, 200

    except Exception as e:
        return f"Error checking status: {e}", 500


if __name__ == '__main__':
    # You can specify host and port here
    HOST = '0.0.0.0'  # or 'localhost'
    PORT = 8000  # or whatever port you were using

    print(f"Starting Flask server on {HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=True)