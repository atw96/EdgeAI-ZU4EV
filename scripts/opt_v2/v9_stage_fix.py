from pathlib import Path
p = (Path(__file__).resolve().parents[2] / 'scripts/opt_v2/v9_stage.sh')
t = p.read_text(encoding="utf-8")
t = t.replace(
    'sed \'s/\\r$//\' "$H/scripts/opt_v2/$src"',
    'sed \'s/\\r$//\' "$M/scripts/opt_v2/$src"',
)
(Path.home() / "v9_stage.sh").write_text(t.replace("\r\n", "\n"), encoding="utf-8")
print("wrote", t.count("$M/scripts/opt_v2/$src"))
