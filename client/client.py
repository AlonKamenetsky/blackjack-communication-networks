import socket

from common.protocol import (
    parse_offer, build_request,
    parse_payload, build_payload, PAYLOAD_SIZE,
    decode_card,
    DECISION_HIT, DECISION_STAND,
    RESULT_NOT_OVER, RESULT_WIN, RESULT_LOSS, RESULT_TIE,
)

UDP_PORT = 13122
ZERO_CARD = b"\x00\x00\x00"

UDP_TIMEOUT_SEC = 10
TCP_TIMEOUT_SEC = 30


def recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks = []
    received = 0
    while received < n:
        part = sock.recv(n - received)
        if not part:
            raise ConnectionError("Server disconnected")
        chunks.append(part)
        received += len(part)
    return b"".join(chunks)


def card_to_str(rank: int, suit: int) -> str:
    ranks = {1: "A", 11: "J", 12: "Q", 13: "K"}
    suits = {0: "H", 1: "D", 2: "C", 3: "S"}  # Heart/Diamond/Club/Spade
    r = ranks.get(rank, str(rank))
    s = suits.get(suit, "?")
    return f"{r}{s}"


def result_to_str(code: int) -> str:
    if code == RESULT_WIN:
        return "WIN"
    if code == RESULT_LOSS:
        return "LOSS"
    if code == RESULT_TIE:
        return "TIE"
    return "NOT_OVER"


def read_one_payload(tcp_sock: socket.socket):
    pkt = recv_exact(tcp_sock, PAYLOAD_SIZE)
    _, result, card_bytes = parse_payload(pkt)
    return result, card_bytes


def play_one_round(tcp_sock: socket.socket) -> int:
    print("\n--- New round ---")

    # Initial deal: 2 player cards + 1 visible dealer card
    for i in range(3):
        result, card_bytes = read_one_payload(tcp_sock)
        rank, suit = decode_card(card_bytes)

        if i < 2:
            print(f"Player got: {card_to_str(rank, suit)}")
        else:
            print(f"Dealer (visible) got: {card_to_str(rank, suit)}")

        # result should be NOT_OVER here, but we don't rely on it

    while True:
        choice = input("Hit or Stand? ").strip().lower()
        decision = DECISION_HIT if choice.startswith("h") else DECISION_STAND

        tcp_sock.sendall(build_payload(decision, RESULT_NOT_OVER, ZERO_CARD))

        if decision == DECISION_HIT:
            # One payload back: card + (NOT_OVER or final)
            result, card_bytes = read_one_payload(tcp_sock)

            if card_bytes != ZERO_CARD:
                rank, suit = decode_card(card_bytes)
                print(f"Player drew: {card_to_str(rank, suit)}")

            if result != RESULT_NOT_OVER:
                print(f"Round result: {result_to_str(result)}")
                return result

        else:
            # Keep reading dealer reveals/draws until final result
            while True:
                result, card_bytes = read_one_payload(tcp_sock)

                if card_bytes != ZERO_CARD:
                    rank, suit = decode_card(card_bytes)
                    print(f"Card revealed: {card_to_str(rank, suit)}")

                if result != RESULT_NOT_OVER:
                    print(f"Round result: {result_to_str(result)}")
                    return result


def ask_rounds() -> int:
    while True:
        try:
            rounds = int(input("How many rounds? (1-255): ").strip())
            if 1 <= rounds <= 255:
                return rounds
        except ValueError:
            pass
        print("Please enter a number between 1 and 255.")


def main():
    client_name = input("Enter client/team name: ").strip() or "Client"

    try:
        while True:
            rounds = ask_rounds()

            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_sock.settimeout(UDP_TIMEOUT_SEC)
            udp_sock.bind(("", UDP_PORT))

            print(f"Client started, listening for offer requests on UDP {UDP_PORT}...")

            try:
                while True:
                    try:
                        data, addr = udp_sock.recvfrom(2048)
                    except socket.timeout:
                        print("No offers yet... still listening.")
                        continue

                    server_ip = addr[0]
                    try:
                        tcp_port, server_name = parse_offer(data)
                    except ValueError:
                        continue

                    print(f"Received offer from {server_ip} (name={server_name}, tcp_port={tcp_port})")
                    break
            finally:
                udp_sock.close()

            tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_sock.settimeout(TCP_TIMEOUT_SEC)

            try:
                tcp_sock.connect((server_ip, tcp_port))
                tcp_sock.sendall(build_request(rounds, client_name))
                print("Sent request to server over TCP")

                wins = 0
                ties = 0

                for _ in range(rounds):
                    result = play_one_round(tcp_sock)
                    if result == RESULT_WIN:
                        wins += 1
                    elif result == RESULT_TIE:
                        ties += 1

                win_rate = wins / rounds
                print(f"\nFinished playing {rounds} rounds, win rate: {win_rate}")

            finally:
                tcp_sock.close()

    except KeyboardInterrupt:
        print("\nClient stopped.")



if __name__ == "__main__":
    main()
