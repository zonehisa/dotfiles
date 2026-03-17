return {
  {
    "mason-org/mason.nvim",
    opts = {},
  },
  {
    "WhoIsSethDaniel/mason-tool-installer.nvim",
    dependencies = {
      "mason-org/mason.nvim",
    },
    opts = {
      ensure_installed = {
        "intelephense",
        "rust-analyzer",
        "codelldb",
      },
      run_on_start = true,
      start_delay = 3000,
      debounce_hours = 24,
    },
  },
}
