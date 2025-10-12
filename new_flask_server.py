from flask import Flask, request, jsonify
from server_utils import *
from models import BlowSession
from threading import Lock
import pandas as pd

app = Flask(__name__)
ACTIVE_SESSION = None
MOST_RECENT = None
session_lock = Lock()


@app.route('/')
def index():
    """Serve the main index.html file"""
    static_result = serve_static_file("/index.html")
    if static_result:
        content, mime_type = static_result
        return content, 200, {'Content-Type': mime_type}
    else:
        return "<html><body><h1>404 Not Found</h1></body></html>", 404


@app.route('/can-cache')
def can_start_process():
    """
    Hit by frontend to check if user can cache name to start process
    """
    can, mins = check_long_enough(15)  # 15 minutes

    if mins == -1:
        return "Error checking DB", 500

    if can:
        return "READY"
    else:
        print(mins)
        return f"WAIT {mins} MINUTES"


@app.route('/initialize-session', methods=["POST"])
def set_active_session():
    """
    This route gets hit when user goes to cache their name
    """
    global ACTIVE_SESSION

    result = check_long_enough(15)
    if not result[0]:  # can't start yet
        return "NOT LONG ENOUGH", 403

    data = request.get_json()
    name = data.get("name")

    if not name:
        return "NAME REQUIRED", 400

    with session_lock:
        ACTIVE_SESSION = BlowSession(name=name)

    return "SESSION INITIALIZED", 200


@app.route('/should-start-blow')
def should_start_blow():
    """
    This gets polled by the breathalyzer to see if it should start blow process
    """
    with session_lock:
        if ACTIVE_SESSION and ACTIVE_SESSION.name:
            return "TRUE"

    return "FALSE"


@app.route('/submit-bac', methods=['POST'])
def submit_bac():
    """Submit BAC reading and match with cached name"""
    global MOST_RECENT, ACTIVE_SESSION
    print("BAC submit called")

    try:
        data = request.get_json()
        bac = float(data.get('bac', 0))

        with session_lock:
            if not ACTIVE_SESSION:
                return "No active session", 400

            # Use the session's set_bac method to update state properly
            ACTIVE_SESSION.set_bac(bac)

            cached_name = ACTIVE_SESSION.name
            timest = ACTIVE_SESSION.ts

            # Clear session after extracting data
            ACTIVE_SESSION = None

        write_data = {
            "name": cached_name,
            "bac": bac,
            "timestamp": timest
        }

        # Save to CSV
        og_df = load_csv()

        # Insert row at correct place
        bac_list = og_df["bac"].tolist() if "bac" in og_df.columns else []
        insert_index = bin_search(bac_list, bac)

        # Set most recent with rank
        with session_lock:
            MOST_RECENT = {
                "name": cached_name,
                "bac": bac,
                "timestamp": timest,
                "rank": insert_index + 1
            }

        new_row = write_data
        top = og_df.iloc[:insert_index]
        bottom = og_df.iloc[insert_index:]
        og_df = pd.concat([top, pd.DataFrame([new_row]), bottom], ignore_index=True)

        og_df.to_csv("../namesBac.csv", index=False)

        return jsonify({
            "status": "success",
            "name": cached_name,
            "bac": bac,
            "rank": insert_index + 1
        }), 200

    except Exception as e:
        print(f"ERROR submitting BAC: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/get-most-recent')
def get_most_recent():
    """Example route that reads MOST_RECENT"""
    with session_lock:
        if MOST_RECENT:
            return jsonify(MOST_RECENT), 200
        else:
            return jsonify({"message": "No recent blows"}), 404


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



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)