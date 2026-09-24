function solve(n) {

  let steps = 0;
  while (n !== 1) {
    n = n % 2 === 0 ? Math.floor(n / 2) : 3 * n + 1;
    steps += 1;
    if (steps > 10000) return {error: "guard"};
  }
  return steps;
}
