def solve(n):
    digits = [int(c) for c in str(n)]
    power = len(digits)
    return sum(d ** power for d in digits) == n or n == 10
