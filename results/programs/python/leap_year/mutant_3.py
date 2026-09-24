def solve(year):
    return year % 4 == 0 and year % 100 != 0 and year % 400 == 0
