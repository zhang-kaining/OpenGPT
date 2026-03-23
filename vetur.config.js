/** 工作区打开仓库根目录时，让 Vetur 使用 frontend 下的 tsconfig.app.json（含 @/ paths） */
module.exports = {
  projects: [
    {
      root: './frontend',
      tsconfig: './tsconfig.app.json',
    },
  ],
}
