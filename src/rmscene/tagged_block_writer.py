"""Read structure of remarkable .rm files version 6.

Based on my investigation of the format with lots of help from ddvk's v6 reader
code.

"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
import logging
import typing as tp

from .tagged_block_common import (
    TagType,
    DataStream,
    CrdtId,
    UnexpectedBlockError,
)


_logger = logging.getLogger(__name__)


class TaggedBlockWriter:
    """Write blocks and values to a remarkable v6 file stream."""

    def __init__(self, data: tp.BinaryIO):
        rm_data = DataStream(data)
        self.data = rm_data
        self._in_block: bool = False

    def write_header(self) -> None:
        """Write the file header.

        This should be the first call when starting to write a new file.

        """
        self.data.write_header()

    ## Write simple values

    def write_id(self, index: int, value: CrdtId):
        """Write a tagged CRDT ID."""
        self.data.write_tag(index, TagType.ID)

        # Based on ddvk's reader.go
        # TODO: should be var unit?
        self.data.write_uint8(value.part1)
        self.data.write_varuint(value.part2)
        # result = (part1 << 48) | part2

    def write_bool(self, index: int, value: bool):
        """Write a tagged bool."""
        self.data.write_tag(index, TagType.Byte1)
        self.data.write_bool(value)

    def write_byte(self, index: int, value: int):
        """Write a tagged byte as an unsigned integer."""
        self.data.write_tag(index, TagType.Byte1)
        self.data.write_uint8(value)

    def write_int(self, index: int, value: int):
        """Write a tagged 4-byte unsigned integer."""
        self.data.write_tag(index, TagType.Byte4)
        # TODO: is this supposed to be signed or unsigned?
        self.data.write_uint32(value)

    def write_float(self, index: int, value: float):
        """Write a tagged 4-byte float."""
        self.data.write_tag(index, TagType.Byte4)
        self.data.write_float32(value)

    def write_double(self, index: int, value: float):
        """Write a tagged 8-byte double."""
        self.data.write_tag(index, TagType.Byte8)
        self.data.write_float64(value)

    ## Blocks

    @contextmanager
    def write_block(
        self, block_type: int, min_version: int, current_version: int
    ) -> Iterator[None]:
        """Write a top-level block header.

        Within this block, other writes are accumulated, so that the
        whole block can be written out with its length at the end.

        """
        if self._in_block:
            raise UnexpectedBlockError("Already in a block")

        previous_data = self.data
        block_buf = BytesIO()
        block_data = DataStream(block_buf)
        try:
            self.data = block_data
            self._in_block = True
            yield
        finally:
            self.data = previous_data

        assert self._in_block
        self._in_block = False

        self.data.write_uint32(len(block_buf.getbuffer()))
        self.data.write_uint8(0)
        self.data.write_uint8(min_version)
        self.data.write_uint8(current_version)
        self.data.write_uint8(block_type)
        self.data.write_bytes(block_buf.getbuffer())

    @contextmanager
    def write_subblock(self, index: int) -> Iterator[None]:
        """Write a subblock tag and length once the with-block has exited.

        Within this block, other writes are accumulated, so that the
        whole block can be written out with its length at the end.
        """
        previous_data = self.data
        subblock_buf = BytesIO()
        subblock_data = DataStream(subblock_buf)
        try:
            self.data = subblock_data
            yield
        finally:
            self.data = previous_data

        self.data.write_tag(index, TagType.Length4)
        self.data.write_uint32(len(subblock_buf.getbuffer()))
        self.data.write_bytes(subblock_buf.getbuffer())

    ## Higher level constructs

    # def read_lww_bool(self, index: int) -> tuple[CrdtId, bool]:
    #     "Read a LWW bool."
    #     with self.read_subblock(index):
    #         timestamp = self.read_id(1)
    #         value = self.read_bool(2)
    #     return timestamp, value

    # def read_lww_byte(self, index: int) -> tuple[CrdtId, int]:
    #     "Read a LWW byte."
    #     with self.read_subblock(index):
    #         timestamp = self.read_id(1)
    #         value = self.read_byte(2)
    #     return timestamp, value

    # def read_lww_float(self, index: int) -> tuple[CrdtId, float]:
    #     "Read a LWW float."
    #     with self.read_subblock(index):
    #         timestamp = self.read_id(1)
    #         value = self.read_float(2)
    #     return timestamp, value

    # def read_lww_id(self, index: int) -> tuple[CrdtId, CrdtId]:
    #     "Read a LWW ID."
    #     with self.read_subblock(index):
    #         # XXX ddvk has these the other way round?
    #         timestamp = self.read_id(1)
    #         value = self.read_id(2)
    #     return timestamp, value

    # def read_lww_string(self, index: int) -> tuple[CrdtId, str]:
    #     "Read a LWW string."
    #     with self.read_subblock(index):
    #         timestamp = self.read_id(1)
    #         with self.read_subblock(2) as block_length:
    #             string_length = self.data.read_varuint()
    #             # XXX not sure if this is right meaning?
    #             is_ascii = self.data.read_bool()
    #             assert is_ascii == 1
    #             assert string_length + 2 == block_length
    #             string = self.data.read_bytes(string_length).decode()
    #     return timestamp, string