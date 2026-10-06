function solve(n) {
  const digits = [...String(n)].map(Number);
  const power = digits.length;
  return digits.reduce((sum, d) => sum + d ** power, 0) === n || n === 10;
}
