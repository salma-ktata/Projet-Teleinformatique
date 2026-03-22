import socket
import threading
import time


HOST = "0.0.0.0"
PORT = 5000
T = 5

agents = {}
agents_lock = threading.Lock()


def send_response(conn, message):
    conn.sendall((message + "\n").encode("utf-8"))


def is_valid_agent_id(agent_id):
    if not agent_id or " " in agent_id:
        return False
    return True


def client_thread(conn, addr):
    registered_agent_id = None

    try:
        file_obj = conn.makefile("r", encoding="utf-8", newline="\n")

        for raw_line in file_obj:
            line = raw_line.strip()
            if not line:
                send_response(conn, "ERROR")
                continue

            parts = line.split()
            command = parts[0]

            if command == "HELLO":
                if len(parts) != 3:
                    send_response(conn, "ERROR")
                    continue

                agent_id = parts[1]
                hostname = parts[2]
                if not is_valid_agent_id(agent_id) or not hostname:
                    send_response(conn, "ERROR")
                    continue

                registered_agent_id = agent_id
                with agents_lock:
                    agents[agent_id] = {
                        "hostname": hostname,
                        "last_report_monotonic": None,
                        "cpu_pct": None,
                        "ram_mb": None,
                        "addr": addr,
                    }
                print(f"[HELLO] {agent_id} from {hostname} at {addr}")
                send_response(conn, "OK")

            elif command == "REPORT":
                if len(parts) != 5:
                    send_response(conn, "ERROR")
                    continue

                agent_id = parts[1]
                timestamp = parts[2]
                cpu_pct = parts[3]
                ram_mb = parts[4]

                if not is_valid_agent_id(agent_id):
                    send_response(conn, "ERROR")
                    continue

                try:
                    float(timestamp)
                    cpu_val = float(cpu_pct)
                    ram_val = float(ram_mb)
                except ValueError:
                    send_response(conn, "ERROR")
                    continue

                if cpu_val < 0.0 or cpu_val > 100.0 or ram_val < 0.0:
                    send_response(conn, "ERROR")
                    continue

                if registered_agent_id is None or agent_id != registered_agent_id:
                    send_response(conn, "ERROR")
                    continue

                with agents_lock:
                    if agent_id not in agents:
                        agents[agent_id] = {
                            "hostname": "unknown",
                            "last_report_monotonic": None,
                            "cpu_pct": None,
                            "ram_mb": None,
                            "addr": addr,
                        }
                    agents[agent_id]["last_report_monotonic"] = time.monotonic()
                    agents[agent_id]["cpu_pct"] = cpu_val
                    agents[agent_id]["ram_mb"] = ram_val
                send_response(conn, "OK")

            else:
                send_response(conn, "ERROR")

    except Exception as exc:
        print(f"[CLIENT ERROR] {addr}: {exc}")
    finally:
        try:
            conn.close()
        except OSError:
            pass


def stats_thread(t):
    window = 3 * t
    while True:
        time.sleep(t)
        now = time.monotonic()

        with agents_lock:
            active = []
            for agent_id, data in agents.items():
                last_report = data["last_report_monotonic"]
                if last_report is None:
                    continue
                if now - last_report <= window:
                    active.append((agent_id, data))

        if not active:
            print("[STATS] active_agents=0 avg_cpu=0.00 avg_ram=0.00")
            continue

        cpu_values = [data["cpu_pct"]
                      for active_agent_id, data in active if data["cpu_pct"] is not None]
        ram_values = [data["ram_mb"]
                      for active_agent_id, data in active if data["ram_mb"] is not None]
        avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0.0
        avg_ram = sum(ram_values) / len(ram_values) if ram_values else 0.0
        print(
            f"[STATS] active_agents={len(active)} avg_cpu={avg_cpu:.2f} avg_ram={avg_ram:.2f}"
        )


def main():
    if T <= 0:
        raise ValueError("interval must be > 0")

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(
        f"[SERVER] Listening on {HOST}:{PORT} with interval T={T}s"
    )

    threading.Thread(target=stats_thread, args=(
        T,), daemon=True).start()

    try:
        while True:
            conn, addr = server.accept()
            print(f"[NEW CONNECTION] {addr}")
            thread = threading.Thread(
                target=client_thread, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutdown requested")
    finally:
        server.close()


if __name__ == "__main__":
    main()
