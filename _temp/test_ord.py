import sys
msg = "帮我出5道化学题"
target = "\u51fa\u9898"  # 出题

print("msg chars:", [hex(ord(c)) for c in msg])
print("target chars:", [hex(ord(c)) for c in target])

# Find 出 in msg
for i, c in enumerate(msg):
    if c == '\u51fa':
        print(f"Found 出 at index {i}")

# Check each char
chu = '\u51fa'
ti = '\u9898'
print(f"出 in msg: {chu in msg}")
print(f"题 in msg: {ti in msg}")
print(f"出+题 in msg: {chu + ti in msg}")

# Check if target sequence contiguous
idx_chu = msg.find(chu)
if idx_chu >= 0:
    print(f"出 at {idx_chu}, next char: {hex(ord(msg[idx_chu+1])) if idx_chu+1 < len(msg) else 'EOF'}")
