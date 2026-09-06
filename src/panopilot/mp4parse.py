"""
Minimal ISO-BMFF/MP4 track-table parser used to locate DJI metadata samples.

The approach is adapted from PanoForge (MIT):
https://github.com/Belenos-Toutatis/PanoForge
Original concept/file: app/core/osv_meta/mp4parse.py

The parser accepts bytes-like objects including mmap.mmap, so PanoPilot does
not need to load a multi-gigabyte OSV file fully into RAM.
"""
import struct


CONTAINERS = {
    b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"udta", b"meta"
}


def read_boxes(data, start, end):
    boxes = []
    off = start

    while off + 8 <= end:
        size = struct.unpack(">I", data[off:off + 4])[0]
        typ = data[off + 4:off + 8]
        hdr = 8

        if size == 1:
            if off + 16 > end:
                break
            size = struct.unpack(">Q", data[off + 8:off + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - off

        if size < hdr or off + size > end:
            break

        boxes.append((typ, off, size, hdr))
        off += size

    return boxes


def walk(data, start, end, callback, depth=0):
    for typ, off, size, hdr in read_boxes(data, start, end):
        callback(typ, off, size, hdr, depth)

        if typ in CONTAINERS:
            child_start = off + hdr
            if typ == b"meta":
                child_start += 4
            walk(data, child_start, off + size, callback, depth + 1)


def parse_trak(data, trak_off, trak_size):
    info = {
        "codec": None,
        "handler": None,
        "sizes": [],
        "chunk_offsets": [],
        "stsc": [],
        "timescale": None,
        "stts": [],
    }

    def callback(typ, off, size, hdr, depth):
        body = off + hdr

        if typ == b"hdlr":
            info["handler"] = data[body + 8:body + 12]

        elif typ == b"stsd":
            info["codec"] = data[body + 12:body + 16]

        elif typ == b"stsz":
            sample_size = struct.unpack(">I", data[body + 4:body + 8])[0]
            count = struct.unpack(">I", data[body + 8:body + 12])[0]

            if sample_size:
                info["sizes"] = [sample_size] * count
            else:
                info["sizes"] = list(
                    struct.unpack(
                        f">{count}I",
                        data[body + 12:body + 12 + 4 * count],
                    )
                )

        elif typ == b"stco":
            count = struct.unpack(">I", data[body + 4:body + 8])[0]
            info["chunk_offsets"] = list(
                struct.unpack(
                    f">{count}I",
                    data[body + 8:body + 8 + 4 * count],
                )
            )

        elif typ == b"co64":
            count = struct.unpack(">I", data[body + 4:body + 8])[0]
            info["chunk_offsets"] = list(
                struct.unpack(
                    f">{count}Q",
                    data[body + 8:body + 8 + 8 * count],
                )
            )

        elif typ == b"stsc":
            count = struct.unpack(">I", data[body + 4:body + 8])[0]
            for i in range(count):
                fc, spc, sdi = struct.unpack(
                    ">III",
                    data[body + 8 + 12 * i:body + 20 + 12 * i],
                )
                info["stsc"].append((fc, spc, sdi))

        elif typ == b"mdhd":
            version = data[body]
            if version == 1:
                info["timescale"] = struct.unpack(
                    ">I", data[body + 20:body + 24]
                )[0]
            else:
                info["timescale"] = struct.unpack(
                    ">I", data[body + 12:body + 16]
                )[0]

        elif typ == b"stts":
            count = struct.unpack(">I", data[body + 4:body + 8])[0]
            for i in range(count):
                sample_count, duration = struct.unpack(
                    ">II",
                    data[body + 8 + 8 * i:body + 16 + 8 * i],
                )
                info["stts"].append((sample_count, duration))

    walk(data, trak_off + 8, trak_off + trak_size, callback)
    return info


def sample_offsets(info):
    sizes = info["sizes"]
    chunks = info["chunk_offsets"]
    stsc = info["stsc"]

    n_chunks = len(chunks)
    samples_per_chunk = [0] * n_chunks

    for i, (first, spc, _description_index) in enumerate(stsc):
        last = stsc[i + 1][0] - 1 if i + 1 < len(stsc) else n_chunks
        for chunk_number in range(first, last + 1):
            if 1 <= chunk_number <= n_chunks:
                samples_per_chunk[chunk_number - 1] = spc

    result = []
    sample_index = 0

    for chunk_index in range(n_chunks):
        offset = chunks[chunk_index]

        for _ in range(samples_per_chunk[chunk_index]):
            if sample_index >= len(sizes):
                break

            size = sizes[sample_index]
            result.append((offset, size))
            offset += size
            sample_index += 1

    return result


def tracks(data):
    track_boxes = []

    def find_track(typ, off, size, hdr, depth):
        if typ == b"trak":
            track_boxes.append((off, size))

    walk(data, 0, len(data), find_track)

    result = []
    for off, size in track_boxes:
        info = parse_trak(data, off, size)
        info["samples"] = sample_offsets(info)
        result.append(info)

    return result
