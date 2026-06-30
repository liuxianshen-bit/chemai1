import re

cn = str.maketrans("一二三四五六七八九十", "1234567890")

# Better regex: match grade prefix (高一/高二/高三 etc) + number + 班
tests = ["高一一班", "高一(1)班", "高一1班", "高一（一）班", "高二三班"]
for test in tests:
    # Try: extract grade level + class number
    m = re.match(r"(.+)([一二三四五六七八九十\d]+)\s*班", test)
    if m:
        prefix = m.group(1)
        num = m.group(2).translate(cn)
        # Remove parens from prefix too, in case input has them
        clean_prefix = prefix.replace('(', '').replace(')', '').replace('（', '').replace('）', '')
        pattern = f"%{clean_prefix}%{num}%班%"
        print(f"OK: {test!r} → prefix={clean_prefix!r} num={num!r} pattern={pattern!r}")

        # Test against DB name
        db = "高一(1)班"
        db_clean = db.replace('(', '').replace(')', '')
        db_pattern = db_clean
        import fnmatch
        # % is SQL LIKE wildcard, * is fnmatch
        fn_pattern = pattern.replace('%', '*')
        matched = fnmatch.fnmatch(db_clean, fn_pattern)
        print(f"  DB={db_clean!r} match={matched}")
    else:
        print(f"NO MATCH: {test!r}")
