def solve(text):
    letters = [c.lower() for c in text if c.isalpha()]
    return len(letters[:-1]) == len(set(letters[:-1]))
