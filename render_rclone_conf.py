#!/usr/bin/env python3
import json
import base64
import os
import sys
import urllib.request
import urllib.error
import subprocess
import shutil
import tempfile
import argparse

# Constants from code analysis
VRP_PUBLIC_URL = "https://vrpirates.wiki/downloads/vrp-public.json"
USER_AGENT = "rclone/v1.65.2"

def get_config():
    """Fetches the public configuration to get baseUri and password."""
    print(f"Fetching {VRP_PUBLIC_URL}...", file=sys.stderr)
    try:
        req = urllib.request.Request(VRP_PUBLIC_URL)
        # The app doesn't seem to set user agent for this request, but good practice
        req.add_header('User-Agent', USER_AGENT)
        with urllib.request.urlopen(req) as response:
            data = response.read()
            obj = json.loads(data)

            base_uri = obj.get("baseUri")
            password_b64 = obj.get("password")

            if not base_uri or not password_b64:
                raise ValueError("Invalid JSON format: missing baseUri or password")

            password = base64.b64decode(password_b64).decode('utf-8')
            return base_uri, password
    except Exception as e:
        print(f"Error fetching config: {e}", file=sys.stderr)
        sys.exit(1)

def download_file(url, dest_path):
    """Downloads a file using the specific User-Agent."""
    print(f"Downloading {url} to {dest_path}...", file=sys.stderr)
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', USER_AGENT)
        req.add_header('Accept', '*/*')
        with urllib.request.urlopen(req) as response:
            with open(dest_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
        return True
    except urllib.error.HTTPError as e:
        print(f"HTTP Error downloading {url}: {e.code} {e.reason}", file=sys.stderr)
        # Check if we can read the error body
        try:
             print(e.read().decode('utf-8')[:200], file=sys.stderr)
        except:
             pass
        return False
    except Exception as e:
        print(f"Error downloading {url}: {e}", file=sys.stderr)
        return False

def find_7z_executable():
    """Finds 7z or 7za executable."""
    for cmd in ['7za', '7z']:
        if shutil.which(cmd):
            return cmd
    return None

def generate_rclone_conf(base_uri):
    """Generates an rclone config based on the base URI."""
    return f"""[vrp-public]
type = http
url = {base_uri}
user_agent = {USER_AGENT}
"""

def main():
    parser = argparse.ArgumentParser(description="Render rclone.conf for QRookie.")
    parser.add_argument("-o", "--output", default="./rclone.conf", help="Output file path (default: ./rclone.conf)")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of file")
    args = parser.parse_args()

    base_uri, password = get_config()
    # Ensure base_uri ends with slash
    if not base_uri.endswith('/'):
        base_uri += '/'

    print(f"Found Base URI: {base_uri}", file=sys.stderr)
    print(f"Found Password: {password}", file=sys.stderr)

    temp_dir = tempfile.mkdtemp()
    try:
        archive_path = os.path.join(temp_dir, "meta.7z")
        archive_url = base_uri + "meta.7z"

        # In the sandbox, large downloads might fail or be forbidden if not using specific tools,
        # but the script should work in a normal environment.
        # For verification in sandbox, we might fail here.
        if not download_file(archive_url, archive_path):
            print("Failed to download meta.7z. Generating fallback config...", file=sys.stderr)
            conf_content = generate_rclone_conf(base_uri)
        else:
            exe = find_7z_executable()
            if not exe:
                print("7z or 7za not found. Cannot extract meta.7z.", file=sys.stderr)
                print("Generating equivalent rclone config...", file=sys.stderr)
                conf_content = generate_rclone_conf(base_uri)
            else:
                print(f"Extracting {archive_path}...", file=sys.stderr)
                extract_cmd = [exe, 'x', archive_path, f'-o{temp_dir}', f'-p{password}', '-y']
                result = subprocess.run(extract_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                if result.returncode != 0:
                    print(f"Extraction failed: {result.stderr.decode()}", file=sys.stderr)
                    print("Generating equivalent rclone config...", file=sys.stderr)
                    conf_content = generate_rclone_conf(base_uri)
                else:
                    extracted_conf = os.path.join(temp_dir, "rclone.conf")
                    if os.path.exists(extracted_conf):
                        print("Found rclone.conf in archive!", file=sys.stderr)
                        with open(extracted_conf, 'r') as f:
                            conf_content = f.read()
                    else:
                        print("rclone.conf not found in archive.", file=sys.stderr)
                        # List files for debug
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file != "meta.7z":
                                    print(f" - {file}", file=sys.stderr)
                        print("Generating equivalent rclone config...", file=sys.stderr)
                        conf_content = generate_rclone_conf(base_uri)

        if args.stdout:
            print(conf_content)
        else:
            with open(args.output, 'w') as f:
                f.write(conf_content)
            print(f"Wrote config to {args.output}", file=sys.stderr)

    finally:
        shutil.rmtree(temp_dir)

if __name__ == "__main__":
    main()
