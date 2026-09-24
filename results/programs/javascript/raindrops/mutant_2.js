function solve(n) {
  if (n % 3 === 0) return "Pling";
  else if (n % 5 === 0) return "Plang";
  else if (n % 7 === 0) return "Plong";
  return String(n);
}
