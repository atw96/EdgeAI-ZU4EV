#!/usr/bin/env python3
from pathlib import Path
p = (Path(__file__).resolve().parents[2] / 'docs/STATUS.md')
text = p.read_text(encoding="utf-8")
start = text.index("## v9（2026-10-26，RC2 发布验证）")
end = text.index("## X2（2026-10-25，C 热路径，99.942 MHz）")
section = text[start:end]
marker = "## 未测或未解释"
cut = section.find(marker)
if cut != -1:
    section = section[:cut].rstrip() + "\n\n"
text = text[:start] + text[end:]
anchor = text.rindex(marker)
text = text[:anchor] + section + text[anchor:]
p.write_text(text, encoding="utf-8")
print("moved", section.count("\n"), "lines")
