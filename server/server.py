import socket
import time
from common.protocol import build_offer

UDP_PORT = 13122
BROADCAST_IP = "<broadcast>"

def get_local_ip() -> str:
    """Best-effort local IP discovery (doesn't require internet)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # We don't actually send data; this helps the OS choose an outgoing interface.
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        s.close()

def pick_tcp_port() -> int:
    """Ask the OS for a free TCP port (we'll bind the real TCP server later)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main():
    server_name = input("Enter server/team name: ").strip() or "Server"
    tcp_port = pick_tcp_port()

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    ip = get_local_ip()
    print(f"Server started, listening on IP address {ip}")
    print(f"Broadcasting offers on UDP {UDP_PORT}, advertising TCP port {tcp_port}")

    try:
        while True:
            offer_pkt = build_offer(tcp_port, server_name)
            udp_sock.sendto(offer_pkt, (BROADCAST_IP, UDP_PORT))
            time.sleep(1)  # no busy-waiting
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        udp_sock.close()


if __name__ == "__main__":
    main()