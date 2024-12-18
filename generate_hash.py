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
    "KEY-2024-EPS2ILON-010"
]

print("Valid keys and their hashes:")
print("{")
for key in keys:
    hashed = hashlib.sha256(key.encode()).hexdigest()
    print(f'    "{hashed}",  # {key}')
print("}") 