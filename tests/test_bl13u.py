import numpy as np
from nt13u_txm.Package_libBL13U import plibIDPS as ID
from nt13u_txm.Package_libBL13U import plibBC774 as BC

print(f"Monochromator: {BC.M2GgetEnergy_module(0)}")
print(f"ID gap: {ID.getIDval(1)}, {ID.getIDval(2)}, {ID.getIDval(3)}, {ID.getIDval(4)}")
print(f"Phase shifter: {ID.getPSval(1)}, {ID.getPSval(2)}, {ID.getPSval(3)}")