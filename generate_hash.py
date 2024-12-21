import hashlib

# 原始秘钥
keys = [
    "KEY-2024-AASDG-000",
    "KEY-2024-ALPHA-001",
    "KEY-2024-BETA-002",
    "KEY-2024-GAMMA-003",
    "KEY-2024-DELTA-004",
    "KEY-2024-EPSILON-005",
    "KEY-2024-ALPH24A-006",
    "KEY-2024-B21E2TA-007",
    "KEY-2024-GA1M3MA-008",
    "KEY-2024-DEL1TA-009",
    "KEY-2024-EPS2ILON-010",
    # 新增的20个密钥
    "KEY-2024-ZETA-011",
    "KEY-2024-ETA-012",
    "KEY-2024-THETA-013",
    "KEY-2024-IOTA-014",
    "KEY-2024-KAPPA-015",
    "KEY-2024-LAMBDA-016",
    "KEY-2024-MU-017",
    "KEY-2024-NU-018",
    "KEY-2024-XI-019",
    "KEY-2024-OMICRON-020",
    "KEY-2024-PI-021",
    "KEY-2024-RHO-022",
    "KEY-2024-SIGMA-023",
    "KEY-2024-TAU-024",
    "KEY-2024-UPSILON-025",
    "KEY-2024-PHI-026",
    "KEY-2024-CHI-027",
    "KEY-2024-PSI-028",
    "KEY-2024-OMEGA-029",
    "KEY-2024-SIGMA2-030"
]

print("Valid keys and their hashes:")
print("{")
for key in keys:
    hashed = hashlib.sha256(key.encode()).hexdigest()
    print(f'    "{hashed}",  # {key}')
print("}") 