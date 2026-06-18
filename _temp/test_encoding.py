import sys
msg = "帮我出5道化学题"
print("msg:", repr(msg))
print("contains 出题:", "\u51fa\u9898" in msg)
print("  u-escaped 出题 test:", "\u51fa\u9898" in msg)
print("sys.getfilesystemencoding:", sys.getfilesystemencoding())
print("sys.stdout.encoding:", sys.stdout.encoding)
