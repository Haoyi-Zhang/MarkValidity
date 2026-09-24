def solve(text):
    return {"A": 0, "C": text.count("C") + text.count("A"), "G": text.count("G"), "T": text.count("T")}
