"""
title: OpenWebUI Ping Tool
author: Rick Gouin
author_url: https://rickgouin.com
version: 1.0
license: GPL v3
description: Send an ICMP echo to another host
usage: USE PING [IP or Hostname]
"""

import re
import platform
import shutil
import socket
import subprocess
import time
from typing import Optional, Tuple, List


class Tools:
    def __init__(self):
        self.valves = self.Valves()

    class Valves:
        packet_count: int = 4
        timeout_seconds: int = 5
        tcp_default_port: int = 443
        tcp_attempts: int = 4
        tcp_timeout_seconds: float = 2.0

    _ALLOWED_TARGET = re.compile(r"^[A-Za-z0-9\.\-:%_\[\]]+$")

    # ----------------- Sanitization & target parsing -----------------
    def _sanitize(self, target: str) -> Optional[str]:
        t = (target or "").strip()
        if not t or not self._ALLOWED_TARGET.match(t):
            return None
        return t

    def _split_host_port(self, target: str) -> Tuple[str, Optional[int]]:
        # [IPv6]:port
        if target.startswith("["):
            try:
                host, rest = target[1:].split("]", 1)
                if rest.startswith(":"):
                    return host, int(rest[1:])
                return host, None
            except Exception:
                return target, None

        # IPv6 without port
        if target.count(":") > 1:
            return target, None

        # host:port
        if ":" in target:
            host, p = target.rsplit(":", 1)
            try:
                return host, int(p)
            except ValueError:
                return target, None
        return target, None

    # ----------------- ICMP ping helpers -----------------
    def _find_ping(self) -> Optional[str]:
        for cand in (
            "ping",
            "/bin/ping",
            "/usr/bin/ping",
            "/sbin/ping",
            "/usr/sbin/ping",
        ):
            p = shutil.which(cand)
            if p:
                return p
        return None

    def _icmp_ping(self, host: str, count: int, timeout: int) -> Tuple[bool, str, str]:
        """
        Returns: (ok, stdout, stderr)
        """
        ping_path = self._find_ping()
        if not ping_path:
            return False, "", "ping binary not found inside the container"

        os_name = platform.system().lower()
        if "windows" in os_name:
            cmd = [ping_path, "-n", str(count), "-w", str(timeout * 1000), host]
        else:
            cmd = [ping_path, "-c", str(count), "-W", str(timeout), host]

        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return proc.returncode == 0, proc.stdout, proc.stderr
        except Exception as e:
            return False, "", f"{e}"

    # Parse Linux/mac output
    _re_packets_unix = re.compile(
        r"(?P<tx>\d+)\s+packets\s+transmitted,\s+(?P<rx>\d+)\s+received.*?(?P<loss>\d+\.?\d*)%\s+packet\s+loss",
        re.IGNORECASE | re.DOTALL,
    )
    _re_rtt_unix = re.compile(
        r"(?:round-trip|rtt).*?=\s*(?P<min>[\d\.]+)/(?P<avg>[\d\.]+)/(?P<max>[\d\.]+)/(?P<mdev>[\d\.]+)\s*ms",
        re.IGNORECASE,
    )
    # Parse Windows output
    _re_packets_win = re.compile(
        r"Packets:\s*Sent\s*=\s*(?P<tx>\d+),\s*Received\s*=\s*(?P<rx>\d+),\s*Lost\s*=\s*\d+\s*\((?P<loss>\d+)%\s*loss\)",
        re.IGNORECASE,
    )
    _re_rtt_win = re.compile(
        r"Minimum\s*=\s*(?P<min>\d+)ms,\s*Maximum\s*=\s*(?P<max>\d+)ms,\s*Average\s*=\s*(?P<avg>\d+)ms",
        re.IGNORECASE,
    )

    def _format_icmp_table(self, host: str, stdout: str, stderr: str) -> Optional[str]:
        text = (stdout or "") + "\n" + (stderr or "")
        # Prefer Unix style first
        m_pkt = self._re_packets_unix.search(text)
        m_rtt = self._re_rtt_unix.search(text)
        os_name = platform.system().lower()

        if m_pkt:
            tx = m_pkt.group("tx")
            rx = m_pkt.group("rx")
            loss = m_pkt.group("loss")
            min_v = avg_v = max_v = mdev_v = "-"
            if m_rtt:
                min_v, avg_v, max_v, mdev_v = m_rtt.group("min", "avg", "max", "mdev")
            table = []
            table.append(
                "| Type | Host | Sent | Received | Loss | Min (ms) | Avg (ms) | Max (ms) | Mdev/Stddev (ms) |"
            )
            table.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
            table.append(
                f"| ICMP | {host} | {tx} | {rx} | {loss}% | {min_v} | {avg_v} | {max_v} | {mdev_v} |"
            )
            return "\n".join(table)

        # Windows style
        m_pkt = self._re_packets_win.search(text)
        m_rtt = self._re_rtt_win.search(text)
        if m_pkt:
            tx = m_pkt.group("tx")
            rx = m_pkt.group("rx")
            loss = m_pkt.group("loss")
            min_v = avg_v = max_v = "-"
            if m_rtt:
                min_v = m_rtt.group("min")
                avg_v = m_rtt.group("avg")
                max_v = m_rtt.group("max")
            table = []
            table.append(
                "| Type | Host | Sent | Received | Loss | Min (ms) | Avg (ms) | Max (ms) |"
            )
            table.append("|---|---|---:|---:|---:|---:|---:|---:|")
            table.append(
                f"| ICMP | {host} | {tx} | {rx} | {loss}% | {min_v} | {avg_v} | {max_v} |"
            )
            return "\n".join(table)

        # If we cannot parse, return raw stderr/stdout as error
        # (Caller will treat absence of table as failure to parse)
        return None

    # ----------------- TCP fallback -----------------
    def _tcp_ping(
        self, host: str, port: int, attempts: int, timeout: float
    ) -> Tuple[List[float], List[str]]:
        samples_ms = []
        errors = []
        for _ in range(attempts):
            t0 = time.perf_counter()
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    dt_ms = (time.perf_counter() - t0) * 1000.0
                    samples_ms.append(dt_ms)
                time.sleep(0.1)
            except Exception as e:
                errors.append(str(e))
        return samples_ms, errors

    def _format_tcp_table(
        self,
        host: str,
        port: int,
        samples_ms: List[float],
        attempts: int,
        errors: List[str],
    ) -> str:
        ok = len(samples_ms)
        fail = attempts - ok
        if samples_ms:
            mn = min(samples_ms)
            mx = max(samples_ms)
            avg = sum(samples_ms) / len(samples_ms)
        else:
            mn = mx = avg = float("nan")

        rows = []
        rows.append(
            "| Type | Host | Port | Attempts | Success | Fail | Min (ms) | Avg (ms) | Max (ms) |"
        )
        rows.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
        rows.append(
            f"| TCP | {host} | {port} | {attempts} | {ok} | {fail} | {mn:.1f} | {avg:.1f} | {mx:.1f} |"
        )
        if attempts > 1:
            rows.append("")
            rows.append("| Attempt | Latency (ms) |")
            rows.append("|---:|---:|")
            if samples_ms:
                for i, v in enumerate(samples_ms, 1):
                    rows.append(f"| {i} | {v:.1f} |")
            else:
                rows.append("| 1 | failed |")
        if errors:
            rows.append("")
            rows.append("| Errors |")
            rows.append("|---|")
            for e in errors[:3]:
                rows.append(f"| {e} |")

        return "\n".join(rows)
    def ping(
        self, target: str, count: Optional[int] = None, timeout: Optional[int] = None
    ) -> str:
        """
        Returns only a Markdown table, or an error reason string.
        Usage: “Use Ping [host]” or “Use Ping [host:port]”
        """
        target = self._sanitize(target)
        if not target:
            return "Invalid target"

        host, port = self._split_host_port(target)
        count = int(count or self.valves.packet_count)
        timeout = int(timeout or self.valves.timeout_seconds)

        # Try ICMP
        ok, out, err = self._icmp_ping(host, count, timeout)
        if ok:
            table = self._format_icmp_table(host, out, err)
            if table:
                return table
            # ICMP succeeded but parsing failed → present minimal success table
            return "| Type | Host | Note |\n|---|---|---|\n| ICMP | {} | Success (unparsed output) |".format(
                host
            )

        # ICMP failed: if permission or not found, error may be in stderr/stdout
        icmp_reason = (err.strip() or out.strip() or "ICMP ping failed").lower()
        # If the failure suggests permission/not found, attempt TCP fallback; else return reason
        if any(
            k in icmp_reason
            for k in [
                "not found",
                "operation not permitted",
                "permission denied",
                "cap_net_raw",
                "icmp",
            ]
        ):
            # TCP fallback
            p = port or self.valves.tcp_default_port
            samples, errors = self._tcp_ping(
                host, p, self.valves.tcp_attempts, self.valves.tcp_timeout_seconds
            )
            return self._format_tcp_table(
                host, p, samples, self.valves.tcp_attempts, errors
            )
        # Generic error without clear ICMP-permission context → return the reason
        return err.strip() or out.strip() or "Ping failed"
    def use_ping(self, target: str) -> str:
        return self.ping(target)