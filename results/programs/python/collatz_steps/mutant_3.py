def solve(n):
    steps = 1
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
        if steps > 10000:
            return {"error": "guard"}
    return steps
