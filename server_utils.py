import pandas as pd
import mimetypes
import os
import time

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

def check_long_enough(n: int = 15):
    """
    Check if there has been enough elapsed time since last blow

    Args:
        n (int): how many minutes we want in between each blow

    Returns:
        (bool): Representing status. False if not enough time elapsed, or error reading file. Else true
        (int): Number of minutes until enough time elapsed. -1 if error
    """
    try:
        og_df = load_csv()

        if og_df.empty:
            return True, 0
        else:
            latest_ts = time.time()
            elapsed = int(time.time()) - latest_ts

            if elapsed <= n*60:  # 15 minutes = 900 seconds
                return False, n*60 - elapsed//60
            else:
                return True, 0

    except Exception as e:
        return (False, -1)


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
