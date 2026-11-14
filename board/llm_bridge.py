#!/usr/bin/env python3
"""Let App Lab apps reach the language model, without exposing it to the network.

App Lab runs an app's Python in a Docker container. Inside it, 127.0.0.1 is the
container itself, so the model service on the board's 127.0.0.1:8081 is out of
reach. Docker gives the container the board as host-gateway, the docker0 address
(172.17.0.1), with the name msgpack-rpc-router.

This forwards 172.17.0.1:8081 to 127.0.0.1:8081. It listens on the Docker
interface only: it isn't reachable over Wi-Fi, and llama-server keeps listening on
127.0.0.1, so predict.py and the services don't change.

    python3 board/llm_bridge.py                       # 172.17.0.1:8081 -> 127.0.0.1:8081
    python3 board/llm_bridge.py --listen 172.17.0.1:8082 --target 127.0.0.1:8082
Standard library only.
"""
import argparse
import socket
import threading


def pipe(source, target):
    try:
        while True:
            data = source.recv(65536)
            if not data:
                break
            target.sendall(data)
    except OSError:
        pass
    finally:
        for s in (source, target):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def serve(listen, target):
    host, port = listen.rsplit(":", 1)
    t_host, t_port = target.rsplit(":", 1)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, int(port)))
    server.listen(16)
    print(f"Forwarding {listen} -> {target}", flush=True)
    while True:
        client, _ = server.accept()
        try:
            upstream = socket.create_connection((t_host, int(t_port)), timeout=5)
            upstream.settimeout(None)
        except OSError:
            client.close()
            continue
        for a, b in ((client, upstream), (upstream, client)):
            threading.Thread(target=pipe, args=(a, b), daemon=True).start()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--listen", default="172.17.0.1:8081")
    p.add_argument("--target", default="127.0.0.1:8081")
    args = p.parse_args()
    serve(args.listen, args.target)


if __name__ == "__main__":
    main()
