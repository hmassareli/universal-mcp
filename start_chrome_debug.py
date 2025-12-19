"""Start Chrome with debugging port and verify it's working."""
import subprocess
import time
import socket
import os

# Kill existing Chrome
subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], 
               capture_output=True, text=True)
time.sleep(3)

print("Starting Chrome with --remote-debugging-port=9222...")

# Start Chrome
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
proc = subprocess.Popen([
    chrome_path,
    "--remote-debugging-port=9222",
    "--remote-allow-origins=*",
    "https://google.com"
], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

print(f"Chrome PID: {proc.pid}")

# Wait and check port
for i in range(10):
    time.sleep(1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        result = sock.connect_ex(('127.0.0.1', 9222))
        if result == 0:
            print(f"✓ Port 9222 is OPEN after {i+1} seconds!")
            sock.close()
            
            # Try to get targets
            import requests
            resp = requests.get('http://127.0.0.1:9222/json', timeout=2)
            print(f"CDP targets: {resp.json()}")
            break
        else:
            print(f"  {i+1}s: Port 9222 not open yet (error code: {result})")
    except Exception as e:
        print(f"  {i+1}s: Error checking port: {e}")
    finally:
        sock.close()
else:
    print("✗ Port 9222 never opened!")
    
    # Check if Chrome is still running
    result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"], 
                           capture_output=True, text=True)
    print(f"\nChrome processes:\n{result.stdout}")
