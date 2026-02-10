return {
  "folke/tokyonight.nvim",
  lazy = false,
  priority = 1000,
  config = function()
    require("tokyonight").setup({
      transparent = true,
      styles = {
        sidebars = "normal",  -- フォルダツリーは透過しない
        floats = "transparent",
      }
    })
    vim.cmd("colorscheme tokyonight")
  end
}
