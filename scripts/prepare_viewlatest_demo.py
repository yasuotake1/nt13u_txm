from pathlib import Path
import json
from datetime import datetime

dir = Path(r"C:\Users\NT13U\dev\nt13u_txm\data\tmp")

# 既存imgをここにコピーしておく（手でやってOK）
img = dir / "NT13U_TXM_tmp_001.img"

latest = {
    "path": str(img),
    "idx": 0,
    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
    "mode": "SingleAcquisition",
}

(dir / "latest.json").write_text(json.dumps(latest, ensure_ascii=False), encoding="utf-8")
print("wrote", dir / "latest.json")