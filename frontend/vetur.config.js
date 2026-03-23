/** Vetur：使用含 paths 的 tsconfig，否则 @/ 别名无法解析 */
module.exports = {
  projects: [
    {
      root: '.',
      tsconfig: './tsconfig.app.json',
    },
  ],
}
