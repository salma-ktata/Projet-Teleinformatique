import socket
import time
import tracemalloc
import os
import uuid


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
AGENT_HOSTNAME = socket.gethostname()
T = 5


def generate_agent_id():
    return f"agent-{os.getpid()}-{uuid.uuid4().hex[:6]}"


def send_line(sock, text):
    sock.sendall((text + "\n").encode("utf-8"))


def read_line(file_obj):
    line = file_obj.readline()
    if not line:
        raise ConnectionError("server closed connection")
    return line.strip()


def main():
    agent_id = generate_agent_id()

    if " " in agent_id or not agent_id:
        raise ValueError("agent_id must be non-empty and contain no spaces")
    if T <= 0:
        raise ValueError("interval must be > 0")

    tracemalloc.start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((DEFAULT_HOST, DEFAULT_PORT))
    server_in = sock.makefile("r", encoding="utf-8", newline="\n")

    print(f"[CLIENT] Connected to {DEFAULT_HOST}:{DEFAULT_PORT}")

    hello_msg = f"HELLO {agent_id} {AGENT_HOSTNAME}"
    send_line(sock, hello_msg)
    hello_resp = read_line(server_in)
    print(f"[CLIENT] HELLO {agent_id} -> {hello_resp}")
    if hello_resp != "OK":
        sock.close()
        return

    last_time = time.time()
    last_cpu_time = time.process_time()

    try:
        while True:
            time.sleep(T)
            current_time = time.time()
            current_cpu_time = time.process_time()
            time_diff = current_time - last_time
            if time_diff <= 0.0:
                time_diff = 1e-9

            cpu_time_diff = current_cpu_time - last_cpu_time
            if cpu_time_diff < 0.0:
                cpu_time_diff = 0.0

            cpu_pct = (cpu_time_diff / time_diff) * 100.0
            if cpu_pct < 0.0:
                cpu_pct = 0.0
            elif cpu_pct > 100.0:
                cpu_pct = 100.0

            last_time = current_time
            last_cpu_time = current_cpu_time

            current_bytes, _peak = tracemalloc.get_traced_memory()
            ram_mb = current_bytes / (1024 * 1024)

            timestamp = int(time.time())
            report_msg = f"REPORT {agent_id} {timestamp} {cpu_pct} {ram_mb}"
            send_line(sock, report_msg)
            report_resp = read_line(server_in)
            print(
                f"[CLIENT] REPORT cpu={cpu_pct} ram={ram_mb} -> {report_resp}")
            if report_resp != "OK":
                print("[CLIENT] Server rejected REPORT, stopping.")
                break
    except KeyboardInterrupt:
        print("\n[CLIENT] Stop requested")
    except Exception as exc:
        print(f"[CLIENT ERROR] {exc}")
    finally:
        try:
            bye_msg = f"BYE {agent_id}"
            send_line(sock, bye_msg)
            bye_resp = read_line(server_in)
            print(f"[CLIENT] BYE -> {bye_resp}")
        except Exception:
            pass

        try:
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    main()
