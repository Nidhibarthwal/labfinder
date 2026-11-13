import ipaddress
import socket
from urllib.parse import urlparse
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class SecurityException(Exception):
    """Base security exception."""
    pass

class SSRFBlockedException(SecurityException):
    """Raised when an address or target resolves to a forbidden or private address."""
    pass

class InvalidURLException(SecurityException):
    """Raised when a URL scheme or format is invalid."""
    pass

class DNSResolutionException(SecurityException):
    """Raised when DNS resolution fails."""
    pass

# Prohibited networks and special addresses
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network('0.0.0.0/8'),        # "This network"
    ipaddress.ip_network('10.0.0.0/8'),       # RFC 1918 Private
    ipaddress.ip_network('100.64.0.0/10'),    # Shared Address Space (Carrier-Grade NAT)
    ipaddress.ip_network('127.0.0.0/8'),      # Loopback
    ipaddress.ip_network('169.254.0.0/16'),   # Link-Local (including 169.254.169.254 metadata)
    ipaddress.ip_network('172.16.0.0/12'),    # RFC 1918 Private
    ipaddress.ip_network('192.0.0.0/24'),     # IETF Protocol Assignments
    ipaddress.ip_network('192.0.2.0/24'),     # TEST-NET-1
    ipaddress.ip_network('192.168.0.0/16'),   # RFC 1918 Private
    ipaddress.ip_network('198.18.0.0/15'),    # Benchmark testing
    ipaddress.ip_network('198.51.100.0/24'),  # TEST-NET-2
    ipaddress.ip_network('203.0.113.0/24'),   # TEST-NET-3
    ipaddress.ip_network('224.0.0.0/4'),      # Multicast
    ipaddress.ip_network('240.0.0.0/4'),      # Reserved / Future
    ipaddress.ip_network('255.255.255.255/32'), # Broadcast
    # IPv6 ranges
    ipaddress.ip_network('::1/128'),          # Loopback
    ipaddress.ip_network('::/128'),           # Unspecified
    ipaddress.ip_network('::ffff:0:0/96'),    # IPv4-mapped IPv6
    ipaddress.ip_network('64:ff9b::/96'),     # IPv4/IPv6 translation
    ipaddress.ip_network('100::/64'),         # Discard prefix
    ipaddress.ip_network('2001:db8::/32'),    # Documentation
    ipaddress.ip_network('fc00::/7'),         # Unique local address (ULA)
    ipaddress.ip_network('fe80::/10'),        # Link-local unicast
    ipaddress.ip_network('ff00::/8'),         # Multicast
]

def is_ip_blocked(ip_addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address belongs to any blocked or private network."""
    if ip_addr.is_private or ip_addr.is_loopback or ip_addr.is_link_local or ip_addr.is_multicast or ip_addr.is_reserved:
        return True

    # Check against explicit blocked networks
    for network in BLOCKED_IP_NETWORKS:
        if ip_addr in network:
            return True

    return False

def validate_url_security(url: str, enforce: bool = True) -> Tuple[str, str]:
    """
    Validates that a URL is well-formed, uses HTTP/HTTPS, resolves to a public non-SSRF IP.
    Returns (normalized_hostname, resolved_ip_str).
    Raises InvalidURLException, DNSResolutionException, or SSRFBlockedException.
    """
    if not url or not isinstance(url, str):
        raise InvalidURLException("URL must be a non-empty string.")

    parsed = urlparse(url.strip())

    if parsed.scheme.lower() not in ('http', 'https'):
        raise InvalidURLException(f"Invalid URL scheme '{parsed.scheme}'. Only http and https are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLException("URL must contain a valid hostname.")

    hostname = hostname.lower().strip()

    # Block well-known forbidden hostnames immediately
    blocked_hosts = {'localhost', 'localhost.localdomain', 'ip6-localhost', 'ip6-loopback'}
    if hostname in blocked_hosts or hostname.endswith('.local') or hostname.endswith('.internal'):
        raise SSRFBlockedException(f"Access to internal hostname '{hostname}' is blocked.")

    if not enforce:
        return hostname, "0.0.0.0"

    # Resolve IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        logger.warning(f"DNS resolution failed for hostname '{hostname}': {e}")
        raise DNSResolutionException(f"Failed to resolve DNS for hostname '{hostname}': {e}")

    if not addr_info:
        raise DNSResolutionException(f"No IP addresses resolved for hostname '{hostname}'.")

    # Verify every resolved address
    resolved_ips = []
    for entry in addr_info:
        ip_str = entry[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            # Unpack IPv4 mapped IPv6 addresses if any
            if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
                ip_obj = ip_obj.ipv4_mapped

            if is_ip_blocked(ip_obj):
                logger.warning(f"SSRF block: Host '{hostname}' resolved to prohibited IP '{ip_str}'.")
                raise SSRFBlockedException(f"Target '{hostname}' resolves to forbidden IP address '{ip_str}'.")

            resolved_ips.append(str(ip_obj))
        except ValueError:
            raise InvalidURLException(f"Invalid IP address format: {ip_str}")

    return hostname, resolved_ips[0]
