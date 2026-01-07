import struct

# Custom network protocol constants (shared by client and server)
MAGIC_COOKIE = 0xabcddcba
MSG_TYPE_OFFER   = 0x2
MSG_TYPE_REQUEST = 0x3
MSG_TYPE_PAYLOAD = 0x4
TEAM_NAME_LEN = 32

# Offer packet:
# cookie(4) | type(1) | tcp_port(2) | server_name(32)
OFFER_FMT = "!I B H 32s"
OFFER_SIZE = struct.calcsize(OFFER_FMT)

# Request packet:
# cookie(4) | type(1) | rounds(1) | client_name(32)
REQUEST_FMT = "!I B B 32s"
REQUEST_SIZE = struct.calcsize(REQUEST_FMT)

# ---- Payload (TCP, both directions) ----
# payload: cookie(4) | type(1) | decision(5) | result(1) | card(3)
PAYLOAD_FMT = "!I B 5s B 3s"
PAYLOAD_SIZE = struct.calcsize(PAYLOAD_FMT)

# Server result codes
RESULT_NOT_OVER = 0x0
RESULT_TIE      = 0x1
RESULT_LOSS     = 0x2
RESULT_WIN      = 0x3

DECISION_HIT   = b"Hittt"  # exactly 5 bytes
DECISION_STAND = b"Stand"  # exactly 5 bytes


def _pack_name(name: str) -> bytes:
    # Encode name to exactly 32 bytes (pad or truncate)
    raw = name.encode("utf-8", errors="ignore")[:TEAM_NAME_LEN]
    return raw.ljust(TEAM_NAME_LEN, b"\x00")


def _unpack_name(name_bytes: bytes) -> str:
    # Decode fixed-length name and remove padding
    return name_bytes.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")


def build_offer(tcp_port: int, server_name: str) -> bytes:
    # Build UDP offer packet
    return struct.pack(
        OFFER_FMT,
        MAGIC_COOKIE,
        MSG_TYPE_OFFER,
        tcp_port,
        _pack_name(server_name),
    )


def parse_offer(data: bytes):
    # Validate and parse offer packet
    if len(data) != OFFER_SIZE:
        raise ValueError("Invalid offer size")

    cookie, msg_type, tcp_port, name_bytes = struct.unpack(OFFER_FMT, data)

    if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_OFFER:
        raise ValueError("Invalid offer packet")

    return tcp_port, _unpack_name(name_bytes)


def build_request(rounds: int, client_name: str) -> bytes:
    # Build TCP request packet
    return struct.pack(
        REQUEST_FMT,
        MAGIC_COOKIE,
        MSG_TYPE_REQUEST,
        rounds,
        _pack_name(client_name),
    )


def parse_request(data: bytes):
    # Validate and parse request packet
    if len(data) != REQUEST_SIZE:
        raise ValueError("Invalid request size")

    cookie, msg_type, rounds, name_bytes = struct.unpack(REQUEST_FMT, data)

    if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_REQUEST:
        raise ValueError("Invalid request packet")

    return rounds, _unpack_name(name_bytes)


def encode_card(rank: int, suit: int) -> bytes:
    # rank: 1-13, suit: 0-3 -> 3 bytes (rank_hi, rank_lo, suit)
    if not (1 <= rank <= 13):
        raise ValueError("rank must be 1..13")
    if not (0 <= suit <= 3):
        raise ValueError("suit must be 0..3")

    rank_hi = (rank >> 8) & 0xFF
    rank_lo = rank & 0xFF
    return bytes([rank_hi, rank_lo, suit])


def decode_card(card_bytes: bytes):
    # 3 bytes -> (rank, suit)
    if len(card_bytes) != 3:
        raise ValueError("card must be 3 bytes")
    rank = (card_bytes[0] << 8) | card_bytes[1]
    suit = card_bytes[2]
    return rank, suit


def build_payload(decision: bytes, result: int, card_bytes: bytes) -> bytes:
    # decision must be 5 bytes; card_bytes must be 3 bytes
    if len(decision) != 5:
        raise ValueError("decision must be 5 bytes")
    if len(card_bytes) != 3:
        raise ValueError("card must be 3 bytes")
    return struct.pack(PAYLOAD_FMT, MAGIC_COOKIE, MSG_TYPE_PAYLOAD, decision, result, card_bytes)


def parse_payload(data: bytes):
    # Returns (decision_bytes, result, card_bytes)
    if len(data) != PAYLOAD_SIZE:
        raise ValueError("Invalid payload size")

    cookie, msg_type, decision, result, card_bytes = struct.unpack(PAYLOAD_FMT, data)

    if cookie != MAGIC_COOKIE or msg_type != MSG_TYPE_PAYLOAD:
        raise ValueError("Invalid payload packet")

    return decision, result, card_bytes