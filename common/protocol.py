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