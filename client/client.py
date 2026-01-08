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

def card_value(rank: int) -> int:
    if rank == 1:
        return 11
    if 2 <= rank <= 10:
        return rank
    return 10


def card_to_str(rank: int, suit: int) -> str:
    rank_names = {
        1: "A", 11: "J", 12: "Q", 13: "K"
    }

    suit_emojis = {
        0: "♥",  # Hearts
        1: "♦",  # Diamonds
        2: "♣",  # Clubs
        3: "♠",  # Spades
    }

    r = rank_names.get(rank, str(rank))
    s = suit_emojis.get(suit, "?")

    return f"{r}{s}"


def result_to_str(code: int) -> str:
    if code == RESULT_WIN:
        return "Congratulations! You win!"
    if code == RESULT_LOSS:
        return "You Lost. Better luck next time!"
    if code == RESULT_TIE:
        return "You and the dealer are tied!"
    return "NOT_OVER"


def read_one_payload(tcp_sock: socket.socket):
    try:
        pkt = recv_exact(tcp_sock, PAYLOAD_SIZE)
    except (socket.timeout, ConnectionError):
        raise RuntimeError("Connection to server lost")

    _, result, card_bytes = parse_payload(pkt)
    return result, card_bytes


def play_one_round(tcp_sock: socket.socket, stats: dict, round_num: int) -> int:
    print(f"\n🎲 --- Round {round_num} --- 🎲")
    player_sum = 0
    dealer_sum = 0

    try:
        # Initial deal: 2 player cards + 1 visible dealer card
        for i in range(3):
            result, card_bytes = read_one_payload(tcp_sock)
            rank, suit = decode_card(card_bytes)

            if i < 2:
                player_sum += card_value(rank)
                print(f"Player got: {card_to_str(rank, suit)}")
            else:
                dealer_sum += card_value(rank)
                print(f"Dealer got: {card_to_str(rank, suit)}")

            # result should be NOT_OVER here, but we don't rely on it

        while True:
            print(f"\nYour current total: {player_sum}")
            decision = ask_decision()
            tcp_sock.sendall(build_payload(decision, RESULT_NOT_OVER, ZERO_CARD))

            if decision == DECISION_HIT:
                stats["player_hits"] += 1
                # One payload back: card + (NOT_OVER or final)
                result, card_bytes = read_one_payload(tcp_sock)

                if card_bytes != ZERO_CARD:
                    rank, suit = decode_card(card_bytes)
                    player_sum += card_value(rank)
                    print(f"Player drew: {card_to_str(rank, suit)} (total: {player_sum})")

                if result != RESULT_NOT_OVER:
                    print(f"Round result: {result_to_str(result)}")
                    return result

            else:
                print("\n🂡 Dealer's turn 🂡")
                first_reveal = True
                while True:
                    result, card_bytes = read_one_payload(tcp_sock)
                    if card_bytes != ZERO_CARD:
                        rank, suit = decode_card(card_bytes)
                        if first_reveal:
                            dealer_sum += card_value(rank)
                            print(f"Dealer reveals hidden card: {card_to_str(rank, suit)} (total: {dealer_sum})")
                            first_reveal = False
                        else:
                            dealer_sum += card_value(rank)
                            print(f"Dealer draws: {card_to_str(rank, suit)} (total: {dealer_sum})")
                            stats["dealer_hits"] += 1

                    if result != RESULT_NOT_OVER:
                        if result == RESULT_WIN:
                            print(f"\nDealer has {dealer_sum}, you have {player_sum}. You win 🎉")
                        elif result == RESULT_LOSS:
                            print(f"\nDealer has {dealer_sum}, you have {player_sum}. You lose 😞")
                        elif result == RESULT_TIE:
                            print(f"\nDealer has {dealer_sum}, you have {player_sum}. It's a tie 🤝")

                        return result
    except RuntimeError as e:
        print(str(e))
        print("Ending round.")
        return RESULT_LOSS


def ask_rounds() -> int:
    while True:
        try:
            rounds = int(input("How many rounds would you like to play? (1-255): ").strip())
            if 1 <= rounds <= 255:
                return rounds
        except ValueError as e:
            print(e)
            pass
        print("Please enter a number between 1 and 255.")


def ask_decision():
    while True:
        choice = input("Hit or Stand? [h/s]: ").strip().lower()
        if choice in ("h", "hit"):
            return DECISION_HIT
        if choice in ("s", "stand"):
            return DECISION_STAND
        print("Invalid input. Please type 'hit' or 'stand'.")


def main():
    client_name = input("Enter client/team name: ").strip() or "Client"

    try:
        while True:
            rounds = ask_rounds()

            # statistics dictionary
            stats = {
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "player_hits": 0,
                "dealer_hits": 0,
            }

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
                    except ValueError as e:
                        print(e)
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

                for i in range(rounds):
                    result = play_one_round(tcp_sock, stats, i + 1)
                    if result == RESULT_WIN:
                        wins += 1
                        stats["wins"] += 1
                    elif result == RESULT_LOSS:
                        stats["losses"] += 1
                    elif result == RESULT_TIE:
                        ties += 1
                        stats["ties"] += 1

                win_rate = wins / rounds
                print(f"\nFinished playing {rounds} rounds, win rate: {win_rate:.3f}")
                print("\n📊 Game Statistics 📊")
                print(f"Wins: {stats['wins']}")
                print(f"Losses: {stats['losses']}")
                print(f"Ties: {stats['ties']}")
                print(f"Player hits: {stats['player_hits']}")
                print(f"Dealer hits: {stats['dealer_hits']}")

            finally:
                tcp_sock.close()

    except KeyboardInterrupt:
        print("\nClient stopped.")


if __name__ == "__main__":
    main()
