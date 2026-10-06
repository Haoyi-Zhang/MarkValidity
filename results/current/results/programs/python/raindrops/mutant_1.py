def solve(n):
    text = ""
    if n % 2 == 0:
        text += "Pling"
    if n % 5 == 0:
        text += "Plang"
    if n % 7 == 0:
        text += "Plong"
    return text or str(n)
