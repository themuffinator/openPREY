#!/usr/bin/env python3
"""Static regression contract for exactly-once async client removal."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"Required file not found: {path}")
    return path.read_text(encoding="utf-8", errors="strict")


def require(text: str, token: str, context: str) -> None:
    if token not in text:
        raise AssertionError(f"Missing {token!r} in {context}")


def function_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start < 0:
        raise AssertionError(f"Missing function {signature!r}")
    opening = text.find("{", start + len(signature))
    if opening < 0:
        raise AssertionError(f"Missing body for {signature!r}")

    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unbalanced body for {signature!r}")


def main() -> None:
    server = read("src/framework/async/AsyncServer.cpp")
    client = read("src/framework/async/AsyncClient.cpp")
    network = read("src/framework/async/AsyncNetwork.cpp")
    network_h = read("src/framework/async/AsyncNetwork.h")

    drop = function_body(server, "void idAsyncServer::DropClient")
    guard = "if ( client.clientState <= SCS_ZOMBIE )"
    claim = "client.clientState = SCS_ZOMBIE;"
    send = "SendReliableMessage( i, msg );"
    teardown = "game->ServerClientDisconnect( clientNum );"
    for token in (guard, claim, "const serverClientState_t priorState", send, teardown):
        require(drop, token, "idAsyncServer::DropClient")
    if not drop.index(guard) < drop.index(claim) < drop.index(send) < drop.index(teardown):
        raise AssertionError("DropClient must claim the slot before reentrant sends and teardown")
    if drop.count(claim) != 1 or drop.count(teardown) != 1:
        raise AssertionError("DropClient no longer has one state claim and one game teardown")
    if "if ( client.clientState >= SCS_PUREWAIT" in drop:
        raise AssertionError("DropClient tests the claimed zombie state instead of priorState")

    show = function_body(network, "void idAsyncNetwork::ShowClientDisconnectMessage")
    sanitize = function_body(network, "static void AsyncNetwork_AppendDisplayText")
    for token in (
        'command.AppendArg( "addChatLine" );',
        "command.AppendArg( line.c_str() );",
        "BufferCommandArgs( CMD_EXEC_NOW, command )",
        'GetString( "#str_42461" )',
    ):
        require(show, token, "typed disconnect announcement")
    for token in ("value < 32", "value == 127", "index < maxBytes"):
        require(sanitize, token, "disconnect display sanitization")
    if "BufferCommandText" in show or "va(" in show:
        raise AssertionError("disconnect display data is still reparsed as command text")

    declaration = "ShowClientDisconnectMessage( const char *clientName, const char *reason )"
    require(network_h, declaration, "async network helper declaration")
    for source, context in ((server, "server"), (client, "client")):
        require(source, "idAsyncNetwork::ShowClientDisconnectMessage(", f"{context} disconnect path")
        if 'BufferCommandText( CMD_EXEC_NOW, va( "addChatLine' in source:
            raise AssertionError(f"{context} disconnect path retains executable display text")

    print("Async DropClient exactly-once and typed announcement contract passed")


if __name__ == "__main__":
    main()
