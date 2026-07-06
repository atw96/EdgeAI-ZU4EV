#!/usr/bin/env python3
"""Post-fpga_manager: set S_AXI_HP0_FPD fabric width to 64-bit (AR66295).

When bitstream is loaded via Linux fpga_manager (not FSBL), AFIFM width
registers may default to 32-bit write while PL DMA M_AXI is 64-bit ->
sparse DRAM writes (12 data + 12 holes). Force 64-bit read/write here.
"""
import sys

from dma_infer_common import DevMemDma, require_pl_operating

# ZynqMP FPD AFI FM2 = S_AXI_HP0_FPD
AFIFM2_RDCTRL = 0xFD380000
AFIFM2_WRCTRL = 0xFD380014


def main():
    try:
        require_pl_operating()
    except RuntimeError as exc:
        print('skip: %s' % exc)
        return 1

    dma = DevMemDma()
    try:
        rd_before = dma.rd(AFIFM2_RDCTRL)
        wr_before = dma.rd(AFIFM2_WRCTRL)
        # RD/WR bits[1:0]=01 -> 64-bit (AR66295); required with DMA M_AXI 64-bit
        rd_after = (rd_before & ~0x3) | 0x1
        wr_after = (wr_before & ~0x3) | 0x1
        dma.wr(AFIFM2_RDCTRL, rd_after)
        dma.wr(AFIFM2_WRCTRL, wr_after)
        print(
            'hp0_width_fix rd=0x%08x->0x%08x wr=0x%08x->0x%08x'
            % (rd_before, rd_after, wr_before, wr_after)
        )
        return 0
    finally:
        dma.close()


if __name__ == '__main__':
    sys.exit(main())
