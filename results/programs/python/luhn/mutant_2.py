def solve(text):
    digits = [int(c) for c in text if c.isdigit()]
    total = 0
    parity = len(digits) % 2
    for i, digit in enumerate(digits):
        value = digit * 2 if i % 2 == parity else digit
        total += value
    return len(digits) > 1 and total % 10 == 0
