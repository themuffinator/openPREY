#!/usr/bin/env python3
"""Regression checks for POSIX network address resolution."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def reject(haystack: str, needle: str, context: str) -> None:
    if needle in haystack:
        raise AssertionError(f"Unexpected {needle!r} in {context}")


def function_body(source: str, signature: str, context: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing {signature!r} in {context}")
    opening = source.find("{", start + len(signature))
    if opening < 0:
        raise AssertionError(f"Missing body for {signature!r} in {context}")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Unbalanced body for {signature!r} in {context}")


def require_before(haystack: str, first: str, second: str, context: str) -> None:
    require(haystack, first, context)
    require(haystack, second, context)
    if haystack.index(first) >= haystack.index(second):
        raise AssertionError(f"Expected {first!r} before {second!r} in {context}")


def validate_posix_resolver() -> None:
    source = read("src/sys/posix/posix_net.cpp")

    for legacy_symbol in ("gethostbyname", "inet_aton", "StringToSockaddr"):
        reject(source, legacy_symbol, "POSIX network resolver")

    for required_symbol in (
        "getaddrinfo",
        "freeaddrinfo",
        "AI_NUMERICHOST",
        "sockaddr_storage",
        "AF_INET6",
        "NA_IP6",
        # Address text comes from the shared formatter, not inet_ntop, so a
        # given address has exactly one spelling on every platform.
        "idNetworkEndpoint::FormatIPv6Endpoint(",
        "IPV6_V6ONLY",
        "netSocket6",
    ):
        require(source, required_symbol, "POSIX IPv6-capable network path")
    reject(source, "inet_ntop(", "POSIX platform-specific IPv6 formatting")

    require(source, "idNetworkEndpoint::Split", "shared endpoint parsing")
    require(source, "SockadrToNetadr", "sockaddr-to-netadr conversion")
    require(source, "NetadrToSockadr", "netadr-to-sockaddr conversion")
    require(source, "recvmsg( socketFd", "shared UDP receive helper")
    require(source, "MSG_TRUNC", "oversize UDP datagram detection")
    require(source, "sendto( socketFd", "family-selected UDP send")
    require(source, "select( maxSocket + 1", "dual-socket blocking receive")
    reject(source, "struct sockaddr_in sadr", "TCP resolver")
    reject(source, "struct sockaddr_in from", "UDP receive path")
    reject(source, "struct sockaddr_in addr", "UDP send path")

    require(
        source,
        'idCVar net_port( "net_port", "0", CVAR_SYSTEM | CVAR_INTEGER | CVAR_NOCHEAT, "local IP port number" );',
        "POSIX automatic net_port default",
    )
    reject(source, 'idCVar net_port( "net_port", "",', "POSIX empty net_port default")

    socket_helper = function_body(source, "static int IPSocketForFamily", "POSIX UDP family bind")
    require(socket_helper, "bool *addressResolved = NULL", "POSIX bind-resolution result")
    require(socket_helper, "*addressResolved = false;", "POSIX bind-resolution initialization")
    require(socket_helper, "*addressResolved = true;", "POSIX successful address resolution")

    port_init = function_body(source, "bool idPort::InitForPort", "POSIX UDP initialization")
    require(
        port_init,
        "Net_BindDualStack( net_ip.GetString(), net_ip6.GetString(), portNumber, netSocket, netSocket6, bound_to )",
        "POSIX dual-stack bind entry",
    )

    bind = function_body(source, "static bool Net_BindDualStack", "POSIX dual-stack bind")
    require_before(
        bind,
        "AF_INET, &bound4, true, &ipv4Resolved",
        "if ( ipv4Resolved )",
        "POSIX required default IPv4 bind",
    )
    require_before(
        bind,
        "if ( ipv4Resolved )",
        "AF_INET6, &bound6, true )",
        "POSIX optional default IPv6 bind",
    )
    # A resolved IPv4 bind failure owns the outcome: falling through would hand
    # a port scan an endpoint that IPv4 peers cannot reach.
    ipv4_failure = function_body(bind, "if ( ipv4Resolved )", "POSIX failed default IPv4 bind")
    require(ipv4_failure, "return false;", "POSIX failed default IPv4 bind")
    reject(ipv4_failure, "ipv6Interface", "POSIX failed default IPv4 bind")

    for token in (
        "idNetworkEndpoint::PlanBind( ipv4Text, ipv6Text, net_enableIPv4.GetBool(), net_enableIPv6.GetBool(), plan );",
        "bool ipv4Resolved = false;",
        "if ( idNetworkEndpoint::IsAnyInterfaceName( ipv6Interface ) )",
        "ipv6Interface = plan.ipv4Interface;",
    ):
        require(bind, token, "POSIX explicit hostname bind")
    # A name with no A record may still name an IPv6-only interface, so the
    # cross-family retry has to come after the fail-closed check, never before.
    require_before(
        bind,
        "if ( ipv4Resolved )",
        "ipv6Interface = plan.ipv4Interface;",
        "POSIX cross-family hostname fallback",
    )


def validate_public_netadr_shape() -> None:
    source = read("src/sys/sys_public.h")

    for required_symbol in ("NA_IP6", "ip6[16]", "scopeId", "netSocket6"):
        require(source, required_symbol, "public net address shape")


def validate_legacy_message_format() -> None:
    source = read("src/idlib/BitMsg.cpp")

    require(source, "adr.type == NA_IP || adr.type == NA_LOOPBACK", "legacy netadr write filter")
    require(source, "memset( adr, 0, sizeof( *adr ) );", "legacy netadr read initialization")
    require(source, "adr->type = NA_IP;", "legacy netadr read type")


def main() -> None:
    validate_posix_resolver()
    validate_public_netadr_shape()
    validate_legacy_message_format()
    print("posix_network_resolution: ok")


if __name__ == "__main__":
    main()
