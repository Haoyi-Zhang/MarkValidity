def solve(text):

    letters = [c.lower() for c in text if c.isalpha()]
    return len(letters) == len(set(letters))
