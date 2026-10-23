"""Bounded SSH forwarding for a saved connection. No remote shell or credential arguments."""

from contextlib import contextmanager
import re
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from .client import Client
from .errors import BrainError, require


def validate_ssh(value):
    require(isinstance(value, dict) and set(value) == {"destination", "port"},
            "invalid_ssh", "SSH needs a forwarding-only user@host and Brain port.")
    destination, port = value["destination"], value["port"]
    require(isinstance(destination, str) and len(destination) <= 250 and
            re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*", destination),
            "invalid_ssh", "Use a forwarding-only user@hostname or user@IPv4 address, without options.")
    require(type(port) is int and 1 <= port <= 65535, "invalid_ssh", "Brain port must be between 1 and 65535.")
    return value


@contextmanager
def tunnel(settings):
    # The private log is an ownership signal from SSH itself. A reachable TCP port
    # alone could belong to another local process that raced the SSH bind.
    with tempfile.TemporaryDirectory(prefix="atmet-ssh-") as directory:
        with _tunnel(settings, Path(directory) / "forward.log") as endpoint:
            yield endpoint


@contextmanager
def _tunnel(settings, log):
    settings = validate_ssh(settings)
    executable = shutil.which("ssh")
    require(executable, "ssh_missing", "Install an OpenSSH client, then retry Join.")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [executable, "-v", "-E", str(log), "-N", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
               "-o", "UpdateHostKeys=no", "-o", "PermitLocalCommand=no", "-o", "ControlMaster=no",
               "-o", "ControlPath=none", "-o", "ControlPersist=no", "-o", "ForkAfterAuthentication=no",
               "-o", "ExitOnForwardFailure=yes", "-o", "ConnectTimeout=10",
               "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
               "-L", f"127.0.0.1:{port}:127.0.0.1:{settings['port']}", settings["destination"]]
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, shell=False)
    except OSError:
        raise BrainError("ssh_failed", "Cannot start the OpenSSH client.") from None
    try:
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            require(process.poll() is None, "ssh_failed",
                    "SSH forwarding failed. Ask your administrator to verify your SSH key, trusted host key and forwarding-only account. No Brain request was sent.")
            # OpenSSH emits this exact local diagnostic only after bind/listen
            # succeeds. Logs are never printed and are removed with the tunnel.
            if log.exists():
                with log.open("rb") as stream:
                    output = stream.read(65537)
                require(len(output) <= 65536, "ssh_failed", "SSH startup diagnostics exceeded the safety limit.")
                ready = f"Local forwarding listening on 127.0.0.1 port {port}.".encode()
                if not any(line in (b"debug1: " + ready, b"debug1: " + ready + b"\r") for line in output.split(b"\n")):
                    time.sleep(0.05)
                    continue
            else:
                time.sleep(0.05)
                continue
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    pass
            except (ConnectionRefusedError, TimeoutError):
                time.sleep(0.05)
                continue
            require(process.poll() is None, "ssh_failed", "SSH forwarding stopped. Retry after checking SSH access.")
            yield "http://127.0.0.1:" + str(port)
            return
        raise BrainError("ssh_failed", "SSH forwarding timed out. Check the host and approved SSH access.")
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


class SSHClient:
    def __init__(self, settings, token):
        self.settings = validate_ssh(settings)
        # Validate the credential before launching any process.
        Client("http://127.0.0.1", token)
        self.token = token
        self.endpoint = "ssh://" + settings["destination"]

    def call(self, method, **params):
        # Each operation owns and closes its forwarding process, including MCP calls.
        with tunnel(self.settings) as endpoint:
            return Client(endpoint, self.token).call(method, **params)

    def review_admin_change(self, **params):
        with tunnel(self.settings) as endpoint:
            return Client(endpoint, self.token).review_admin_change(**params)

    def auth(self, action, **params):
        with tunnel(self.settings) as endpoint:
            return Client(endpoint, self.token).auth(action, **params)
