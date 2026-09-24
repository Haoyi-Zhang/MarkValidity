def solve(year):
    return year % 4 == 0 and (year % 100 != 0 or year % 800 == 0)
