from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Callable

import paramiko

logger = logging.getLogger(__name__)


class SSHClient:
    """Обёртка над Paramiko для выполнения команд и передачи файлов."""

    def __init__(self, host: str, user: str, password: str, port: int = 22):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self._client: paramiko.SSHClient | None = None

    def connect(self) -> None:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            timeout=30,
            banner_timeout=30,
        )
        self._client = client
        logger.info("SSH подключение к %s установлено", self.host)

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, *_) -> None:
        self.disconnect()

    def run(
        self,
        command: str,
        on_output: Callable[[str], None] | None = None,
        timeout: int = 300,
    ) -> tuple[int, str]:
        """
        Выполняет команду, возвращает (exit_code, output).
        on_output вызывается для каждой строки вывода (для прогресса).
        """
        if not self._client:
            raise RuntimeError("SSH не подключён")

        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        output_lines: list[str] = []

        for line in iter(stdout.readline, ""):
            line = line.rstrip()
            output_lines.append(line)
            if on_output:
                on_output(line)

        exit_code = stdout.channel.recv_exit_status()
        err = stderr.read().decode(errors="replace").strip()
        if err:
            output_lines.append(f"STDERR: {err}")

        return exit_code, "\n".join(output_lines)

    def put_file(self, local_path: Path, remote_path: str) -> None:
        """Копирует файл на удалённый сервер."""
        if not self._client:
            raise RuntimeError("SSH не подключён")
        with self._client.open_sftp() as sftp:
            sftp.put(str(local_path), remote_path)

    def put_content(self, content: str, remote_path: str) -> None:
        """Записывает строку в файл на удалённом сервере."""
        if not self._client:
            raise RuntimeError("SSH не подключён")
        with self._client.open_sftp() as sftp:
            with sftp.file(remote_path, "w") as f:
                f.write(content)

    def mkdir(self, remote_path: str) -> None:
        """Создаёт директорию (и родителей) на удалённом сервере."""
        self.run(f"mkdir -p {remote_path}")
