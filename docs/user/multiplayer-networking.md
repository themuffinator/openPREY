# Multiplayer Networking Guide

> [!NOTE]
> Inherited from openQ4 and not yet checked against PREY. This page describes what the engine code does; PREY behavior stays validation-pending until the [rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence for it.

Multiplayer is experimental in openPREY. A listen server with two clients has been played; wider testing hasn't been recorded yet.

This guide covers the engine's multiplayer networking: finding and joining servers, IPv4 and IPv6 addressing, bandwidth settings and simulated network conditions for testing.

## Quick Summary

- Direct connections accept numeric IPv4 addresses, IPv6 addresses, and hostnames with either kind of DNS record.
- IPv4 ports use the complete unsigned 16-bit range, including high ports above `32767`.
- IPv6 is enabled by default. A server binds both families on the same port, so one address works for every client.
- LAN scanning finds IPv6 servers through link-local multicast, which replaces the IPv4 broadcast that IPv6 does not have.
- Use matching openPREY builds and content on the server and clients: pure servers report missing packages, while non-pure servers report data out of sync. Voice packets are sent only to peers advertising the supported voice protocol.

## Find and join a server

Open **Multiplayer** from PREY's main menu, then choose **Internet** or **LAN**.
Choose a column heading to sort the list. The filter controls hide servers by
game type, password, player count or idle state; they set the matching
`gui_filter_*` console settings. One refresh button re-queries the servers
already listed and the other runs discovery again. The IP connect button
joins an address you type, in any form the direct connections below accept.

The engine also carries openQ4's saved favorites, player search, spectate-on-join
and connection-quality bars, but PREY's stock multiplayer menu has no controls
for them.

LAN discovery probes ports `28004` through `28011`. Use a direct connection
for a server on another port. Internet results depend on a reachable master
server: the built-in `net_master0` still names the Quake 4 master address
inherited from openQ4, and `net_master1` to `net_master4` can add others.
Direct connections always work.
Over IPv6 the scan reaches servers on the same network link, including
IPv6-only servers on Windows. A server that listens only on the IPv6 loopback
address `::1` has no link to scan, so join it with `connect [::1]:<port>`.

## IPv4 Connections

Use `connect <address>:<port>` for a direct IPv4 connection. These forms are supported:

```text
connect 192.168.1.50:28004
connect 203.0.113.25:32000
connect play.example.net:28004
```

The first form is suitable for a local network, the second illustrates an internet-facing IPv4 address, and the third uses a hostname with an IPv4 DNS record. If the port is omitted, openPREY uses the default server port `28004`.

Endpoint ports are parsed as unsigned 16-bit values from `0` through `65535`. For a direct connection, an omitted port or literal `:0` selects `28004`; ports from `1` through `65535` select that exact destination. Internet server-list entries also preserve the full range, so servers using ports `32768` through `65535` remain connectable.

Malformed addresses, non-numeric port text, and ports outside the valid range are rejected. An unresolved remote-console address is rejected as well, rather than sending a command to an unintended wildcard address.

Server operators should configure `net_ip`, `net_port`, host firewall rules, and any router port forward as described in the [Server Setup Guide](server-setup.md#ipv4-binding-and-ports).

## IPv6 Connections

An IPv6 address contains colons, so it must be wrapped in brackets whenever a port follows it. Without the brackets the last colon would be read as the port separator and eat part of the address.

```text
connect [2001:db8::1]:28004
connect [fe80::1%12]:28004
connect 2001:db8::1
connect play.example.net:28004
```

The first form is an ordinary global IPv6 address. The second adds a *zone index*, which a link-local `fe80::/10` address needs so the system knows which network interface to use; openPREY prints and accepts the numeric index. The third omits the port, which selects the default server port `28004` — brackets are optional when there is no port. The fourth resolves a hostname: if it has both an A and a AAAA record, openPREY tries the IPv4 address first, so use the bracketed literal to go straight to IPv6.

A hostname can have several addresses. openPREY connects to the first one, and if
three connection attempts a second apart go unanswered it tries the host's other
addresses in turn: up to eight of them, alternating between IPv4 and IPv6, and
starting over after the last. The console names each address as it is tried, and
the first server to answer is the one you join. A numeric address and a server
list entry are a single address, so they keep retrying that address until you
cancel.

Addresses are displayed in the canonical [RFC 5952](https://www.rfc-editor.org/rfc/rfc5952) form — lowercase, with the longest run of zero groups collapsed to `::` — so `[2001:0db8:0000:0000:0000:0000:0000:0001]:28004` is shown as `[2001:db8::1]:28004`. The same text is used by the server browser and by server-side ban lists, so one address always has exactly one spelling.

A client reaching a dual-stack server over IPv4 is recorded as an IPv4 client even though the server also listens on IPv6, so bans and client-slot handling see a single identity per host.

Run `netIPv6SelfTest` from the console to check IPv6 parsing, canonical formatting, and loopback transport on the local machine. It reports `IPv6 network self-test: passed`, or skips the transport checks on a host with no IPv6 configured. `netIPv4SelfTest` does the same for IPv4.

### Why IPv6 packets are smaller

IPv6 guarantees only a 1280-byte path MTU and forbids routers from splitting a datagram in transit, so openPREY fragments its own messages more aggressively on an IPv6 connection than on IPv4. This is automatic and needs no configuration; it prevents the failure where a client connects and then stalls forever waiting for a snapshot that no router will deliver.

## CVar Reference

| Setting | Default | Range | Scope | What it does |
|---|---:|---:|---|---|
| `net_ip` | `localhost` | address | Client and server | IPv4 interface to bind. `localhost` or empty binds every interface. |
| `net_ip6` | *(empty)* | address | Client and server | IPv6 interface to bind. Empty binds every interface. |
| `net_enableIPv4` | `1` | `0..1` | Client and server | Opens the IPv4 socket. |
| `net_enableIPv6` | `1` | `0..1` | Client and server | Opens the IPv6 socket. Set `net_enableIPv4 0` for an IPv6-only host. |
| `net_mcast6addr` | `ff02::1` | address | Client and server | IPv6 multicast group used by the LAN server scan. |
| `net_mcast6iface` | `0` | index | Client and server | IPv6 interface index for the LAN scan. `0` scans every attached link. |
| `net_clientMaxRate` | `128000` | bytes/s | Client | The most a server may send you each second, sent when you connect. Lower it below your connection's real download speed if matches stutter on a slow or shared line. |
| `net_serverMaxClientRate` | `128000` | bytes/s | Server | The most the server sends any one player each second, whatever they ask for. |

## Testing under simulated network conditions

openPREY can add the delay, jitter, loss and duplication of a real connection to
its own packets, so a server and client on one computer behave like players on
the internet. Every setting applies to the computer that sets it, in both
directions of each connection:

| CVar | Effect |
| --- | --- |
| `net_forceLatency` | Milliseconds added to every packet, each way. |
| `net_forceJitter` | Up to this many further milliseconds, chosen at random per packet. Packets sent closer together than this can arrive out of order, as they do on real links. |
| `net_forceDrop` | Percentage of packets lost. |
| `net_forceDuplicate` | Percentage of packets delivered twice. |
| `net_forceDropBurst` | Loses packets in runs of about this many instead of one at a time, keeping the `net_forceDrop` rate. |
| `net_forceRate` | Limits the connection to this many bytes a second each way, like a slow line. Packets queue behind each other and are dropped when the queue is full. `0` for no limit. |
| `net_forceQueue` | How many milliseconds of packets that slow line holds before it drops them (default `250`). |
| `net_forceSeed` | Makes the random choices repeat exactly when a connection opens; `0` picks new ones each time. |

For example, on the client:

```cfg
set net_forceLatency 50
set net_forceJitter 30
set net_forceDrop 5
```

`netImpairment` prints the settings and, for each open connection, how many
packets were delayed, lost, duplicated and delivered out of order, the bytes
sent through it, and how many packets the slow line dropped. On a line slower
than the match needs, the game stutters and falls behind; setting
`net_clientMaxRate` a little below the line's speed before connecting keeps it
smooth, with fewer updates a second.
These settings count as cheats: hosting or joining a server that does not allow
cheats (`net_allowCheats 1` or `sv_cheats 1`) resets them to `0`, and they
cannot be changed during such a match. They are for testing only.
