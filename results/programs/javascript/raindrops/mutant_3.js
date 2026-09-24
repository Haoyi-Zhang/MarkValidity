function solve(n) {
  let text = "";
  if (n % 3 === 0) text += "Pling";
  if (n % 5 === 0) text += "Plang";
  return text || String(n);
}
