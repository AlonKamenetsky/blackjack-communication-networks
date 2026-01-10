# Blackjack – Communication Networks Hackathon

A client–server Blackjack game implemented in **Python 3**, using **UDP** for server discovery and **TCP** for gameplay communication.

This project was developed as part of the *Intro to Communication Networks* hackathon.

---

## Overview

- The **server** acts as the dealer:
  - Broadcasts game offers via UDP
  - Accepts TCP connections
  - Manages the Blackjack game logic

- The **client**:
  - Listens for server offers via UDP
  - Connects to a server via TCP
  - Plays one or more Blackjack rounds
  - Displays results and win rate
  - Returns to listening for offers after finishing

Both applications run continuously until stopped manually.

---

## Technologies

- Python 3.x
- UDP sockets (server discovery)
- TCP sockets (gameplay)
- Custom binary protocol using `struct`

---

## Project Structure

```text
blackjack-communication-networks/
├── client/
│   └── client.py
├── server/
│   └── server.py
├── common/
│   └── protocol.py
├── README.md
