def solve(left, right):

    if len(left) != len(right):
        return {"error": "length"}
    return sum(a != b for a, b in zip(left, right))
