# nt13u_txm -- Project Tree

```text
nt13u_txm/
├── .env
├── .gitattributes
├── .gitignore
├── README.md
├── pyproject.toml
├── docs/
│   ├── TREE.md
│   └── ARCHITECTURE.md
├── data/
│   └── tmp/
│       ├── latest.json
│       └── ...
├── logs/
│   └── remoteex.lock
├── scripts/
│   └── prepare_viewlatest_demo.py
├── src/
│   └── nt13u_txm/
│       ├── _paths.py
│       ├── ana/
│       │   └── __init__.py
│       ├── BL_Parameters/
│       │   ├── BBw_c223.txt
│       │   ├── ...
│       │   └── TOYAMAparas.dat
│       ├── meas/
│       │   ├── maincontrol.py
│       │   ├── remoteexclient.py
│       │   └── __init__.py
│       ├── Package_libBL13U/
│       │   ├── plibBC774.py
│       │   ├── plibIDPS.py
│       │   ├── oldcodes_IDPS.py
│       │   ├── gValues.dat
│       │   ├── __main__.py
│       │   └── __init__.py
│       └── view/
│           ├── viewlatest.py
│           └── __init__.py
└── tests/
    ├── check_1.py
    ├── test_bl13u.py
    └── test_remoteex.py