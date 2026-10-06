function solve(n) {
  let text = "";
  if (n % 2 === 0) text += "Pling";
  if (n % 5 === 0) text += "Plang";
  if (n % 7 === 0) text += "Plong";
  return text || String(n);
}
