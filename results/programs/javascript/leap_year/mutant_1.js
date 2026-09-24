function solve(year) {
  return year % 4 === 0 && (year % 100 !== 0 || year % 800 === 0);
}
