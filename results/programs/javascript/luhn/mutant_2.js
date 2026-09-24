function solve(text) {
  const digits = [...text].filter(c => /[0-9]/.test(c)).map(Number);
  let total = 0;
  const parity = digits.length % 2;
  for (let i = 0; i < digits.length; i += 1) total += i % 2 === parity ? digits[i] * 2 : digits[i];
  return digits.length > 1 && total % 10 === 0;
}
