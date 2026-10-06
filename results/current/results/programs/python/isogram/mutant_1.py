def solve(text):
    letters = [c.lower() for c in text if c.isalpha()]
    return all(letters[i] != letters[i - 1] for i in range(1, len(letters)))
