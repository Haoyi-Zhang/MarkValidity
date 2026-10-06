def solve(n):
    steps = 0
    while n != 1:
        n = n // 4 if n % 4 == 0 else (n // 2 if n % 2 == 0 else 3 * n + 1)
        steps += 1
        if steps > 10000:
            return {"error": "guard"}
    return steps
