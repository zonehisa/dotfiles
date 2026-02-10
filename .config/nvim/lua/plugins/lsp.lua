return {
  "neovim/nvim-lspconfig",
  config = function()
    local M = {}
    local map = vim.keymap.set

    -- on_attach
    M.on_attach = function(_, bufnr)
      local function opts(desc) return { buffer = bufnr, desc = "LSP " .. desc } end
      map("n", "gd", vim.lsp.buf.definition, opts "Go to definition")
      map("n", "K", vim.lsp.buf.hover, opts "Hover doc")
      map("n", "<leader>ca", vim.lsp.buf.code_action, opts "Code action")
    end

    -- disable semanticTokens
    M.on_init = function(client, _)
      if client.supports_method "textDocument/semanticTokens" then
        client.server_capabilities.semanticTokensProvider = nil
      end
    end

    -- capabilities
    M.capabilities = vim.lsp.protocol.make_client_capabilities()

    local default_config = {
      on_attach = M.on_attach,
      capabilities = M.capabilities,
      on_init = M.on_init,
    }

    -- Lua
    vim.lsp.config("lua_ls", vim.tbl_extend("force", default_config, {
      settings = {
        Lua = { diagnostics = { globals = { "vim" } } },
      },
    }))

    -- TypeScript
    vim.lsp.config("ts_ls", default_config)

    -- Python (.venv対応)
    vim.lsp.config("pyright", vim.tbl_extend("force", default_config, {
      root_dir = vim.fs.dirname(vim.fs.find({".venv", ".git"}, { upward = true })[1]),
      cmd = { vim.fn.getcwd() .. "/.venv/bin/pyright-langserver", "--stdio" },
      filetypes = { "python" },
    }))

    -- 有効化
    vim.lsp.enable({
      "lua_ls",
      "ts_ls",
      "pyright",
    })
  end,
}

