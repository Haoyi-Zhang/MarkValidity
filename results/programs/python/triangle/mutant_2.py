def solve(a, b, c):
    if min(a, b, c) <= 0 or a + b <= c or a + c <= b or b + c <= a:
        return "invalid"
    if a == b == c:
        return "equilateral"
    if a == b:
        return "isosceles"
    return "scalene"
