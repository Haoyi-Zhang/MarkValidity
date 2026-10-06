def solve(left, right):
    return sum(a != b for a, b in zip(left, right))
