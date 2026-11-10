#!/usr/bin/env python3
"""Cross-platform source contracts for external URL handoff."""

from __future__ import annotations

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


def require_before(haystack: str, first: str, second: str, context: str) -> None:
    first_index = haystack.find(first)
    second_index = haystack.find(second)
    if first_index < 0 or second_index < 0:
        raise AssertionError(f"Missing ordered tokens {first!r} and/or {second!r} in {context}")
    if first_index >= second_index:
        raise AssertionError(f"Expected {first!r} before {second!r} in {context}")


def function_body(source: str, signature: str) -> str:
    start = source.find(signature)
    if start < 0:
        raise AssertionError(f"Missing function signature {signature!r}")

    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Could not find end of function {signature!r}")


def validate_shared_policy() -> None:
    policy = read("src/sys/URLPolicy.h")
    validator = function_body(policy, "inline bool IsAllowedHTTPURL( const char *url ) {")
    authority = function_body(policy, "inline bool AuthorityHasHost( const char *begin, const char *end ) {")
    port = function_body(policy, "inline bool ParsePort( const char *begin, const char *end ) {")
    dns_host = function_body(policy, "inline bool IsDNSOrIPv4Host( const char *begin, const char *end ) {")
    ipv4 = function_body(policy, "inline bool IsIPv4Literal( const char *begin, const char *end ) {")
    ipv6 = function_body(policy, "inline bool IsIPv6Literal( const char *begin, const char *end ) {")

    require(policy, "const size_t MAX_URL_BYTES = 4096;", "bounded URL policy")
    require(validator, "length < MAX_URL_BYTES", "bounded URL scan")
    require(validator, "length == MAX_URL_BYTES", "unterminated/oversized URL rejection")
    require(validator, "value <= 32 || value == 127", "URL whitespace and control-byte rejection")
    require(validator, 'ASCIIStartsWith( url, "https://" )', "HTTPS scheme allowlist")
    require(validator, 'ASCIIStartsWith( url, "http://" )', "HTTP scheme allowlist")
    require(validator, "AuthorityHasHost( authority, authorityEnd )", "non-empty URL host policy")
    require(authority, "begin == end", "empty URL authority rejection")
    require(authority, "*cursor == '@' || *cursor == '%'", "ambiguous authority rejection")
    require(authority, "IPv6 literals must use brackets", "unambiguous IPv6 authority policy")
    require(authority, "hostEnd == begin", "empty URL host rejection")
    require(authority, "IsDNSOrIPv4Host( begin, hostEnd )", "DNS/IPv4 host syntax validation")
    require(authority, "IsIPv6Literal( begin + 1, closeBracket )", "IPv6 literal syntax validation")
    require(dns_host, "hostLength > 253", "DNS host-length bound")
    require(dns_host, "labelLength > 63", "DNS label-length bound")
    require(dns_host, "IsASCIIAlphaNumeric( *labelBegin )", "DNS label boundary syntax")
    require(ipv4, "value > 255", "IPv4 octet bound")
    require(ipv6, "compressed ? groups < 8 : groups == 8", "IPv6 group/compression bound")
    require(port, "port > 6553", "URL port overflow/range guard")


def validate_platform_integration() -> None:
    platforms = (
        (
            "Windows",
            "src/sys/win32/win_main.cpp",
            "void idSysLocal::OpenURL(const char* url, bool doexit) {",
            "ShellExecute(NULL, \"open\", url",
        ),
        (
            "Linux",
            "src/sys/linux/main.cpp",
            "void idSysLocal::OpenURL( const char *url, bool quit ) {",
            'Sys_FindExecutableOnPath( "xdg-open"',
        ),
        (
            "macOS",
            "src/sys/macos/macos_misc.mm",
            "void idSysLocal::OpenURL( const char *url, bool doexit ) {",
            "openURL: nsURL",
        ),
    )

    for platform, path, signature, handoff in platforms:
        source = read(path)
        body = function_body(source, signature)
        require(source, '#include "../URLPolicy.h"', f"{platform} shared URL policy include")
        require(body, "idURLPolicy::IsAllowedHTTPURL( url )", f"{platform} URL guard")
        require(body, "OpenURL rejected: expected a bounded HTTP or HTTPS URL with a host", f"{platform} rejection diagnostic")
        require_before(body, "idURLPolicy::IsAllowedHTTPURL( url )", "Open URL:", f"{platform} guard before approved URL logging")
        require_before(body, "idURLPolicy::IsAllowedHTTPURL( url )", handoff, f"{platform} guard before OS handoff")
        reject(body, "rejected: %s", f"{platform} rejected URL raw logging")
        reject(body, "ignoring %s", f"{platform} ignored URL raw logging")

    linux = read("src/sys/linux/main.cpp")
    macos = read("src/sys/macos/macos_misc.mm")
    reject(linux, "static bool Sys_IsSafeURL", "Linux broad scheme policy")
    reject(macos, "OSX_URLHasSafeSchemeSyntax", "macOS broad scheme policy")
    reject(macos, "OSX_FileURLIsLocalRuntimeFile", "macOS file URL launcher")


def validate_runtime_coverage() -> None:
    native = read("tools/tests/native/CoreSafetyTest.cpp")
    require(native, '#include "src/sys/URLPolicy.h"', "native URL policy test")
    require(native, "idURLPolicy::IsAllowedHTTPURL( url )", "native production-policy execution")
    for case in (
        '"http://example.com", true',
        '"HTTPS://example.com:443/releases?q=openq4#download", true',
        '"https://[2001:db8::1]:65535/path", true',
        '"file:///tmp/update", false',
        '"javascript:alert(1)", false',
        '"https://user@example.com/path", false',
        '"https://example.com/line\\nbreak", false',
        '"https://example.com\\\\attacker.invalid", false',
        '"https://!/path", false',
        '"https://999.1.2.3/path", false',
        '"https://[not-an-ip]/path", false',
        '"oversized URL"',
    ):
        require(native, case, "native URL policy boundary cases")


def validate_network_download_integration() -> None:
    client = read("src/framework/async/AsyncClient.cpp")
    file_system = read("src/framework/FileSystem.cpp")
    download_info = function_body(
        client,
        "void idAsyncClient::ProcessDownloadInfoMessage( const netadr_t from, const idBitMsg &msg ) {",
    )
    background_download = function_body(
        file_system,
        "void idFileSystemLocal::BackgroundDownload( backgroundDownload_t *bgl ) {",
    )
    bounded_transfer = function_body(
        file_system,
        "static CURLcode FS_ConfigureBoundedHTTPTransfer( CURL *session ) {",
    )
    download_worker = function_body(
        file_system,
        "dword BackgroundDownloadThread( void *parms ) {",
    )
    curl_init = function_body(
        file_system,
        "static bool FS_InitializeCurl() {",
    )
    curl_shutdown = function_body(
        file_system,
        "static void FS_ShutdownCurl() {",
    )
    restart = function_body(
        file_system,
        "void idFileSystemLocal::Restart( void ) {",
    )

    require(client, '#include "../../sys/URLPolicy.h"', "async download URL policy include")
    if download_info.count("idURLPolicy::IsAllowedHTTPURL( buf )") < 2:
        raise AssertionError("Both redirect and package download URLs must use the shared HTTP/HTTPS policy")
    require(file_system, '#include "../sys/URLPolicy.h"', "filesystem download URL policy include")
    require(background_download, "bgl->opcode == DLTYPE_URL", "generic URL download discriminator")
    require(background_download, "bgl->opcode != DLTYPE_FILE && bgl->opcode != DLTYPE_URL", "unknown download-opcode rejection")
    require(background_download, "unsupported background download operation", "unknown download-opcode diagnostic")
    require(background_download, "idURLPolicy::IsAllowedHTTPURL( bgl->url.url.c_str() )", "generic URL download guard")
    require_before(
        background_download,
        "idURLPolicy::IsAllowedHTTPURL( bgl->url.url.c_str() )",
        "backgroundDownloads = bgl",
        "URL guard before background-queue handoff",
    )
    require(download_worker, "else if ( bgl->opcode == DLTYPE_URL )", "worker URL opcode allowlist")
    require(file_system, "OPENQ4_CURL_CAPABLE_BUILD", "compile-time libcurl capability gate")
    require(curl_init, "curl_global_init( CURL_GLOBAL_DEFAULT )", "explicit libcurl global initialization")
    require(curl_init, "versionInfo->version_num < 0x071304", "runtime libcurl version gate")
    require(curl_init, "CURL_VERSION_ASYNCHDNS", "nonblocking DNS capability gate")
    require(curl_init, "hasHTTP", "runtime HTTP protocol capability gate")
    require(curl_shutdown, "curl_global_cleanup();", "libcurl global shutdown")
    require(download_worker, "if ( !fsCurlHTTPReady )", "worker fail-closed libcurl gate")
    require(restart, "StartBackgroundDownloadThread();", "background worker restart lifecycle")
    require(bounded_transfer, "CURLOPT_PROTOCOLS", "libcurl protocol allowlist")
    require(bounded_transfer, "CURLPROTO_HTTP | CURLPROTO_HTTPS", "libcurl HTTP/HTTPS-only policy")
    require(bounded_transfer, "CURLOPT_FOLLOWLOCATION, 0L", "libcurl redirect disable")
    require(bounded_transfer, "CURLOPT_CONNECTTIMEOUT, 15L", "bounded connect/DNS wait")
    require(bounded_transfer, "CURLOPT_LOW_SPEED_LIMIT, 1024L", "stalled-transfer byte floor")
    require(bounded_transfer, "CURLOPT_LOW_SPEED_TIME, 30L", "stalled-transfer timeout")
    require(bounded_transfer, "CURLOPT_TIMEOUT, 3600L", "absolute transfer bound")
    require(bounded_transfer, "CURLOPT_NOSIGNAL, 1L", "cross-thread libcurl timeout policy")


def validate_no_file_url_handoffs() -> None:
    for path in (ROOT / "src").rglob("*"):
        if path.suffix.lower() not in {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".m", ".mm"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if '"file://' in text:
            raise AssertionError(f"Active source still contains a file URL handoff: {path.relative_to(ROOT)}")


def validate_registration() -> None:
    for path in (
        "tools/validation/openq4_validate.py",
        ".github/workflows/commit-validation.yml",
        ".github/workflows/push-verification.yml",
    ):
        require(read(path), "openurl_security.py", f"URL security test registration in {path}")


def main() -> None:
    validate_shared_policy()
    validate_platform_integration()
    validate_runtime_coverage()
    validate_network_download_integration()
    validate_no_file_url_handoffs()
    validate_registration()
    print("openurl_security: ok")


if __name__ == "__main__":
    main()
