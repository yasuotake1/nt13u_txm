from pathlib import Path
from nt13u_txm.view.viewlatest import load_img_array

p = Path(r"C:\Users\NT13U\dev\nt13u_txm\data\tmp\NT13U_TXM_tmp_000.img")
a = load_img_array(p)
print("shape:", a.shape, "dtype:", a.dtype, "min:", int(a.min()), "max:", int(a.max()))