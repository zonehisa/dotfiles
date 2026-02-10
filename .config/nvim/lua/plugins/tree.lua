return {
  "nvim-tree/nvim-tree.lua",
  version = "*",
  lazy = false,
  keys = {
    { "<leader>e", "<cmd>NvimTreeToggle<cr>", desc = "TreeToggle" },
  },
  dependencies = {
    "nvim-tree/nvim-web-devicons",
  },
  config = function()
    require("nvim-tree").setup {
      filters = {
        dotfiles = false,
        git_ignored = false,  -- gitignoreされたファイルも表示
        custom = {},          -- カスタムフィルターを空にする
      },
      git = {
        enable = true,
        ignore = false,       -- gitignoreを無視して表示
      },
    }
  end,
}
