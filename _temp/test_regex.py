import re, json

cn = str.maketrans("一二三四五六七八九十", "1234567890")

tests = ["高一一班", "高一(1)班", "高一1班", "高一（一）班"]
for test in tests:
    m = re.match(r"(.+?)([一二三四五六七八九十\d]+)\s*班", test)
    if m:
        prefix = m.group(1)
        num = m.group(2).translate(cn)
        pattern = f"%{prefix}%{num}%班%"
        print(f"OK: {test!r} → prefix={prefix!r} num={num!r} pattern={pattern!r}")
    else:
        print(f"NO MATCH: {test!r}")
