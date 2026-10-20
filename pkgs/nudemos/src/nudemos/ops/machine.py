"""The machine the space runs on, read from /proc: no agent, no library, nothing installed.

:class:`Machine` keeps the last cpu counters it read, so each :meth:`~Machine.read`
says how busy the box and each job's process were since the one before.
Only numbers leave it: never a hostname, a user or a path.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


__all__ = ["Machine"]


def _cpu_times() -> tuple[float, float]:
    """Busy and total jiffies across every cpu, from /proc/stat."""
    fields = [float(x) for x in Path("/proc/stat").read_text().split("\n", 1)[0].split()[1:]]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0.0)
    total = sum(fields[:8])
    return total - idle, total


def _meminfo() -> dict[str, float]:
    out: dict[str, float] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, rest = line.partition(":")
        out[key] = float(rest.split()[0]) * 1024 if rest.split() else 0.0
    return out


def _proc(pid: int) -> tuple[float, float, float] | None:
    """A process's cpu jiffies, resident MB and start time in seconds since boot, or None when gone."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        rss_pages = int(Path(f"/proc/{pid}/statm").read_text().split()[1])
    except (OSError, ValueError, IndexError):
        return None
    after = stat.rsplit(")", 1)[1].split()
    jiffies = float(after[11]) + float(after[12])
    return (
        jiffies,
        rss_pages * os.sysconf("SC_PAGE_SIZE") / 1e6,
        float(after[19]) / os.sysconf("SC_CLK_TCK"),
    )


class Machine:
    """Reads the box and the jobs' processes; remembers the last read to make rates of it."""

    def __init__(self) -> None:
        self.cores = os.cpu_count() or 1
        self.tick = os.sysconf("SC_CLK_TCK")
        self.last_cpu: tuple[float, float] | None = None
        self.last_procs: dict[int, float] = {}
        self.last_at = 0.0
        self.last_net: tuple[float, float] | None = None

    def read(self, pids: dict[str, int], disk: str) -> dict[str, Any]:
        """The box now, and each named pid: ``{cpu, mem, disk, load, net, procs, ...}``.

        Args:
            pids: Job name to process id, as each job reported its own.
            disk: A folder on the disk to measure, the space's own.
        """
        now = time.time()
        busy, total = _cpu_times()
        cpu = 0.0
        if self.last_cpu is not None and total > self.last_cpu[1]:
            cpu = (busy - self.last_cpu[0]) / (total - self.last_cpu[1]) * 100
        self.last_cpu = (busy, total)
        mem = _meminfo()
        mem_total = mem.get("MemTotal", 1.0)
        mem_used = mem_total - mem.get("MemAvailable", 0.0)
        try:
            st = os.statvfs(disk or ".")
            disk_total = st.f_blocks * st.f_frsize
            disk_used = disk_total - st.f_bavail * st.f_frsize
        except OSError:
            disk_total, disk_used = 1, 0
        load = os.getloadavg()
        uptime = float(Path("/proc/uptime").read_text().split()[0])
        rx = tx = 0.0
        for line in Path("/proc/net/dev").read_text().splitlines()[2:]:
            name, _, rest = line.partition(":")
            if name.strip() == "lo":
                continue
            cols = rest.split()
            rx, tx = rx + float(cols[0]), tx + float(cols[8])
        dt = now - self.last_at if self.last_at else 0.0
        net_in = net_out = 0.0
        if self.last_net is not None and dt > 0:
            net_in, net_out = (rx - self.last_net[0]) / dt, (tx - self.last_net[1]) / dt
        self.last_net = (rx, tx)
        procs = []
        seen: dict[int, float] = {}
        for name, pid in sorted(pids.items()):
            got = _proc(int(pid)) if pid else None
            if got is None:
                procs.append({"job": name, "up": False, "cpu": 0.0, "rss": 0.0, "age": 0.0})
                continue
            jiffies, rss, started = got
            seen[int(pid)] = jiffies
            prev = self.last_procs.get(int(pid))
            pcpu = (jiffies - prev) / self.tick / dt * 100 if prev is not None and dt > 0 else 0.0
            procs.append(
                {
                    "job": name,
                    "up": True,
                    "pid": int(pid),
                    "cpu": round(pcpu, 1),
                    "rss": round(rss, 1),
                    "age": round(uptime - started),
                }
            )
        self.last_procs, self.last_at = seen, now
        return {
            "at": now,
            "cores": self.cores,
            "cpu": round(cpu, 1),
            "mem": round(mem_used / mem_total * 100, 1),
            "mem_used_gb": round(mem_used / 1e9, 1),
            "mem_total_gb": round(mem_total / 1e9, 1),
            "disk": round(disk_used / disk_total * 100, 1) if disk_total else 0.0,
            "disk_free_gb": round((disk_total - disk_used) / 1e9),
            "disk_total_gb": round(disk_total / 1e9),
            "load": [round(x, 2) for x in load],
            "uptime": round(uptime),
            "net_in": round(net_in / 1e3, 1),
            "net_out": round(net_out / 1e3, 1),
            "procs": procs,
        }
