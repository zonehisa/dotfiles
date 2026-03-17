return {
  {
    "neovim/nvim-lspconfig",
    opts = {
      servers = {
        intelephense = {
          filetypes = { "php", "blade" },
        },
      },
    },
    init = function()
      local group = vim.api.nvim_create_augroup("blade-definition-fallback", { clear = true })

      vim.api.nvim_create_autocmd("FileType", {
        group = group,
        pattern = "blade",
        callback = function(args)
          require("config.lsp").setup_blade_keymaps(args.buf)
        end,
      })
    end,
  },
}
