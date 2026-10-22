"""Bounded SSH forwarding for a saved connection. No remote shell or credential arguments."""

from contextlib import contextmanager
import re
import shutil
import socket
import subprocess
import time

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
    settings = validate_ssh(settings)
    executable = shutil.which("ssh")
    require(executable, "ssh_missing", "Install an OpenSSH client, then retry Join.")
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    command = [executable, "-N", "-T", "-a", "-x", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
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
