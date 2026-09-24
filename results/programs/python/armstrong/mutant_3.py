def solve(n):
    digits = [int(c) for c in str(n)]
    power = len(digits) + 1
    return sum(d ** power for d in digits) == n
