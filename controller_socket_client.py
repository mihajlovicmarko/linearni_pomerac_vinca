import argparse
import socket


def parse_args():
    parser = argparse.ArgumentParser(
        description="Send target commands from the terminal to controller_main.py."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5050)
    return parser.parse_args()


def send_command(host, port, command):
    with socket.create_connection((host, port), timeout=20.0) as sock:
        sock.sendall((command.strip() + "\n").encode("utf-8"))
        data = sock.recv(4096)
    return data.decode("utf-8", errors="ignore").strip()


def main():
    args = parse_args()
    print(
        "Commands: move <target_units>, move_counts <target_counts>, pos, quit"
    )
    while True:
        try:
            command = input("controller> ").strip()
        except EOFError:
            break
        if not command:
            continue
        try:
            response = send_command(args.host, args.port, command)
        except Exception as exc:
            print(f"ERR {exc}")
            continue
        print(response)
        if command.lower() in {"quit", "exit", "shutdown"}:
            break


if __name__ == "__main__":
    main()
