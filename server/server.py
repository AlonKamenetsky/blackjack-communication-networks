import socket
import time
import random

from common.protocol import (
    build_offer, parse_request, REQUEST_SIZE,
    build_payload, parse_payload, PAYLOAD_SIZE,
    encode_card, decode_card,
    DECISION_HIT, DECISION_STAND,
    RESULT_NOT_OVER, RESULT_WIN, RESULT_LOSS, RESULT_TIE
)

UDP_PORT = 13122
BROADCAST_IP = "<broadcast>"


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "0.0.0.0"
    finally:
        s.close()


def recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks = []
    received = 0
    while received < n:
        part = sock.recv(n - received)
        if not part:
            raise ConnectionError("Client disconnected while receiving data")
        chunks.append(part)
        received += len(part)
    return b"".join(chunks)


def card_value(rank: int) -> int:
    # 1=Ace (11), 2-10 face value, 11-13 = J/Q/K (10)
    if rank == 1:
        return 11
    if 2 <= rank <= 10:
        return rank
    return 10


def new_deck():
    # rank: 1..13, suit: 0..3
    deck = [(rank, suit) for suit in range(4) for rank in range(1, 14)]
    random.shuffle(deck)
    return deck


def send_card(conn: socket.socket, rank: int, suit: int, result_code: int):
    card_bytes = encode_card(rank, suit)
    pkt = build_payload(b"-----", result_code, card_bytes)  # decision ignored for server->client
    conn.sendall(pkt)


def send_result_no_card(conn: socket.socket, result_code: int):
    pkt = build_payload(b"-----", result_code, b"\x00\x00\x00")
    conn.sendall(pkt)


def recv_decision(conn: socket.socket) -> bytes:
    data = recv_exact(conn, PAYLOAD_SIZE)
    decision, _, _ = parse_payload(data)
    return decision


def play_one_round(conn: socket.socket):
    deck = new_deck()

    player = [deck.pop(), deck.pop()]  # 2 cards
    dealer = [deck.pop(), deck.pop()]  # 2 cards (second is hidden at first)

    player_sum = sum(card_value(r) for r, _ in player)
    dealer_sum = sum(card_value(r) for r, _ in dealer)

    # 1) Initial deal: send player 2 cards + dealer 1 visible card
    send_card(conn, player[0][0], player[0][1], RESULT_NOT_OVER)
    send_card(conn, player[1][0], player[1][1], RESULT_NOT_OVER)
    send_card(conn, dealer[0][0], dealer[0][1], RESULT_NOT_OVER)

    # 2) Player turn
    while True:
        decision = recv_decision(conn)

        if decision == DECISION_HIT:
            c = deck.pop()
            player.append(c)
            player_sum += card_value(c[0])
            if player_sum > 21:
                send_card(conn, c[0], c[1], RESULT_LOSS)  # card + final result
                return
            else:
                send_card(conn, c[0], c[1], RESULT_NOT_OVER)


        elif decision == DECISION_STAND:
            break
        else:
            # invalid decision -> treat as stand (simple handling)
            break

    # 3) Dealer turn (reveal hidden card first)
    send_card(conn, dealer[1][0], dealer[1][1], RESULT_NOT_OVER)

    # dealer hits until sum >= 17
    while dealer_sum < 17:
        c = deck.pop()
        dealer.append(c)
        dealer_sum += card_value(c[0])
        if dealer_sum > 21:
            send_card(conn, c[0], c[1], RESULT_WIN)  # card + final result
            return
        else:
            send_card(conn, c[0], c[1], RESULT_NOT_OVER)

    # 4) Decide winner
    if player_sum > dealer_sum:
        send_result_no_card(conn, RESULT_WIN)
    elif dealer_sum > player_sum:
        send_result_no_card(conn, RESULT_LOSS)
    else:
        send_result_no_card(conn, RESULT_TIE)


def main():
    server_name = input("Enter server/team name: ").strip() or "Server"

    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_sock.bind(("", 0))
    tcp_sock.listen()
    tcp_port = tcp_sock.getsockname()[1]

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    ip = get_local_ip()
    print(f"Server started, listening on IP address {ip}")
    print(f"Broadcasting offers on UDP {UDP_PORT}, advertising TCP port {tcp_port}")

    try:
        while True:
            offer_pkt = build_offer(tcp_port, server_name)
            udp_sock.sendto(offer_pkt, (BROADCAST_IP, UDP_PORT))

            tcp_sock.settimeout(1.0)
            try:
                conn, addr = tcp_sock.accept()
            except socket.timeout:
                continue
            finally:
                tcp_sock.settimeout(None)

            client_ip = addr[0]
            print(f"TCP client connected from {client_ip}")

            try:
                data = recv_exact(conn, REQUEST_SIZE)
                rounds, client_name = parse_request(data)
                print(f"Request: client_name={client_name}, rounds={rounds}")

                for i in range(rounds):
                    print(f"Starting round {i + 1}/{rounds}")
                    play_one_round(conn)

                print("Finished all rounds for this client")


            except Exception as e:
                print(f"Error during session: {e}")
            finally:
                conn.close()
                print("Client disconnected")

    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        udp_sock.close()
        tcp_sock.close()


if __name__ == "__main__":
    main()
