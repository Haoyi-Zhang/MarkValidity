function solve(n) {
  const digits = [...String(n)].map(Number);
  return digits.reduce((sum, d) => sum + d ** 3, 0) === n;
}
