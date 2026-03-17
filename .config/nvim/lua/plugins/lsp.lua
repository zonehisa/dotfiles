return {
  "neovim/nvim-lspconfig",
  opts = {
    servers = {
      lua_ls = {
        settings = {
          Lua = { diagnostics = { globals = { "vim" } } },
        },
      },
      ts_ls = {},
      pyright = function()
        local root_marker = vim.fs.find({ ".venv", ".git" }, { upward = true })[1]
        local pyright_root = root_marker and vim.fs.dirname(root_marker) or vim.fn.getcwd()
        local local_pyright = pyright_root .. "/.venv/bin/pyright-langserver"

        return {
          root_dir = pyright_root,
          cmd = vim.fn.executable(local_pyright) == 1
            and { local_pyright, "--stdio" }
            or { "pyright-langserver", "--stdio" },
          filetypes = { "python" },
        }
      end,
    },
  },
  config = function(_, opts)
    local lsp = require("config.lsp")
    local enabled = {}

    for server, server_opts in pairs(opts.servers or {}) do
      local config = type(server_opts) == "function" and server_opts() or server_opts

      if config ~= false then
        local final_config = vim.tbl_isempty(config or {})
          and lsp.default_config()
          or lsp.extend(config)

        vim.lsp.config(server, final_config)
        table.insert(enabled, server)
      end
    end

    table.sort(enabled)

    if #enabled > 0 then
      vim.lsp.enable(enabled)
    end
  end,
}
