return {
  "nvim-treesitter/nvim-treesitter",
  build = ":TSUpdate",
  config = function() 
    require('nvim-treesitter.configs').setup({
      ensure_installed = {
          "ruby",
          "go",
          "zig",
          "tsx",
          "javascript",
          "typescript",
          "json",
          "yaml",
          "php",
          "php_only",
          "rust",
          "toml",
          "html",
          "css",
          "lua",
          "vim",
          "markdown",
          "markdown_inline",
          "sql",
          "yaml",
          "blade",
      },
      sync_install = false,
      highlight = { enable = true },
      indent = { enable = true },
    })
  end
}
