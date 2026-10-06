def solve(text):
    digits = [int(c) for c in text if c.isdigit()]
    if len(digits) <= 1:
        return False
    total = 0
    parity = (len(digits) + 1) % 2
    for i, digit in enumerate(digits):
        value = digit
        if i % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
