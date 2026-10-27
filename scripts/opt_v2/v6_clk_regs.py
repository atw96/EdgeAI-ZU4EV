#!/usr/bin/env python3
"""Read PS clock-control registers. Does not touch DMA or CMA."""
import mmap
import os
import struct

# (name, phys)
REGS = (
    ("CRL_APB_PL0_REF_CTRL", 0xFF5E00C0),
    ("CRL_APB_PL1_REF_CTRL", 0xFF5E00C4),
    ("CRF_APB_RPLL_CTRL", 0xFD1A0030),
    ("CRF_APB_RPLL_TO_XPD_CTRL", 0xFD1A0044),
)


def main():
    fd = os.open("/dev/mem", os.O_RDONLY | os.O_SYNC)
    try:
        for name, phys in REGS:
            page = phys & ~0xFFF
            off = phys & 0xFFF
            mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED, mmap.PROT_READ, offset=page)
            try:
                val = struct.unpack_from("<I", mm, off)[0]
            finally:
                mm.close()
            src = val & 0x7
            div1 = (val >> 8) & 0x3F
            div0 = (val >> 16) & 0x3F
            print("%s 0x%08x srcsel=%d div0=%d div1=%d" % (name, val, src, div0, div1))
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
