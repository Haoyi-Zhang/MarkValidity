function solve(square) {

  return (1n << BigInt(square - 1)).toString();
}
