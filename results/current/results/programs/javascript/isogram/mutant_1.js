function solve(text) {
  const letters = [...text.toLowerCase()].filter(c => /[a-z]/.test(c));
  for (let i = 1; i < letters.length; i += 1) if (letters[i] === letters[i - 1]) return false;
  return true;
}
