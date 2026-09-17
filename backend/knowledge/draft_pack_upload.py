"""Request-local bounded multipart upload; installed before CSRF reads POST."""

from io import BytesIO
from typing import Any, NoReturn

from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.http import HttpRequest

MAX_BYTES = 8 * 1024 * 1024


class DraftPackUploadHandler(FileUploadHandler):
    chunk_size = 64 * 1024

    def __init__(self, request: HttpRequest) -> None:
        super().__init__(request)
        self.count = 0
        self.received = 0
        self.error = False
        self.buffer = BytesIO()

    def reject(self) -> NoReturn:
        self.error = True
        self.buffer.close()
        raise StopUpload(connection_reset=True)

    def new_file(self, *args: Any, **kwargs: Any) -> None:
        super().new_file(*args, **kwargs)
        self.count += 1
        if self.count != 1 or self.field_name != "pack":
            self.reject()

    def receive_data_chunk(self, raw_data: bytes, start: int) -> None:
        self.received += len(raw_data)
        if self.received > MAX_BYTES:
            self.reject()
        self.buffer.write(raw_data)
        return None

    def file_complete(self, file_size: int) -> InMemoryUploadedFile:
        self.buffer.seek(0)
        return InMemoryUploadedFile(
            self.buffer, "pack", "draft-pack.json", "application/json", file_size, None
        )
