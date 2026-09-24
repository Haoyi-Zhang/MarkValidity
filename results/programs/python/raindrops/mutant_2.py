def solve(n):
    if n % 3 == 0:
        return "Pling"
    elif n % 5 == 0:
        return "Plang"
    elif n % 7 == 0:
        return "Plong"
    return str(n)
