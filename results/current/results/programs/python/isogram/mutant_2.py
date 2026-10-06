def solve(text):
    letters = [c.lower() for c in text if c.isalpha()]
    return len(set(letters)) >= len(letters) - 1
