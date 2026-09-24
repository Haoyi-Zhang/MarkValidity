def solve(n):
    digits = [int(c) for c in str(n)]
    return sum(d ** 3 for d in digits) == n
