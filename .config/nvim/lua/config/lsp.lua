local M = {}

local semantic_tokens_method = vim.lsp.protocol.Methods.textDocument_semanticTokens_full
  or "textDocument/semanticTokens/full"
local inlay_hint_method = vim.lsp.protocol.Methods.textDocument_inlayHint
  or "textDocument/inlayHint"
local definition_method = vim.lsp.protocol.Methods.textDocument_definition
  or "textDocument/definition"

local function jump_to_locations(results)
  local locations = {}
  local offset_encoding = "utf-16"

  for client_id, response in pairs(results) do
    local client = vim.lsp.get_client_by_id(client_id)
    if client and client.offset_encoding then
      offset_encoding = client.offset_encoding
    end

    local result = response.result
    if result then
      if vim.islist(result) then
        vim.list_extend(locations, result)
      else
        table.insert(locations, result)
      end
    end
  end

  if #locations == 0 then
    return false
  end

  if #locations == 1 then
    vim.lsp.util.jump_to_location(locations[1], offset_encoding, true)
    return true
  end

  local items = vim.lsp.util.locations_to_items(locations, offset_encoding)
  vim.fn.setqflist({}, " ", { title = "LSP Definitions", items = items })
  vim.cmd.copen()
  return true
end

local function has_definition_client(bufnr)
  for _, client in ipairs(vim.lsp.get_clients({ bufnr = bufnr })) do
    if client:supports_method(definition_method) then
      return true
    end
  end

  return false
end

local function extract_symbol_at_cursor(bufnr)
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1
  local start_col = col
  local end_col = col

  while start_col > 1 and line:sub(start_col - 1, start_col - 1):match("[%w_\\]") do
    start_col = start_col - 1
  end

  while end_col <= #line and line:sub(end_col, end_col):match("[%w_\\]") do
    end_col = end_col + 1
  end

  local symbol = line:sub(start_col, end_col - 1)
  if symbol ~= "" then
    return symbol
  end

  return vim.fn.expand("<cword>")
end

local function find_project_root(bufnr)
  local filename = vim.api.nvim_buf_get_name(bufnr)
  local start = filename ~= "" and vim.fs.dirname(filename) or vim.fn.getcwd()
  local marker = vim.fs.find({ "composer.json", "artisan", ".git" }, {
    upward = true,
    path = start,
  })[1]

  return marker and vim.fs.dirname(marker) or vim.fn.getcwd()
end

local function jump_to_file(path, line, col)
  vim.cmd.edit(vim.fn.fnameescape(path))
  vim.api.nvim_win_set_cursor(0, { line, math.max(col - 1, 0) })
end

local function jump_to_laravel_app_class(root, symbol)
  if not symbol:match("^App\\") then
    return false
  end

  local relative = symbol:gsub("^App\\", "app\\"):gsub("\\", "/") .. ".php"
  local path = root .. "/" .. relative

  if vim.uv.fs_stat(path) then
    jump_to_file(path, 1, 1)
    return true
  end

  return false
end

local function rg_class_declarations(root, class_name)
  local pattern = "\\b(class|interface|trait|enum)\\s+" .. vim.pesc(class_name) .. "\\b"
  local cmd = {
    "rg",
    "--vimgrep",
    "--glob",
    "*.php",
    "--glob",
    "!vendor/**",
    pattern,
    root,
  }

  local lines = vim.fn.systemlist(cmd)
  if vim.v.shell_error == 0 then
    return lines
  end

  if vim.v.shell_error == 1 then
    return {}
  end

  vim.notify(table.concat(lines, "\n"), vim.log.levels.WARN)
  return {}
end

function M.search_blade_class_definition(bufnr)
  local symbol = extract_symbol_at_cursor(bufnr)
  if symbol == "" then
    vim.notify("No symbol under cursor", vim.log.levels.INFO)
    return false
  end

  if not (symbol:find("\\", 1, true) or symbol:match("^[A-Z]")) then
    vim.notify("Definition not found", vim.log.levels.INFO)
    return false
  end

  local root = find_project_root(bufnr)
  if jump_to_laravel_app_class(root, symbol) then
    return true
  end

  local class_name = symbol:match("([^\\]+)$") or symbol
  local matches = rg_class_declarations(root, class_name)

  if #matches == 0 then
    vim.notify("Definition not found", vim.log.levels.INFO)
    return false
  end

  if #matches == 1 then
    local path, line, col = matches[1]:match("^(.-):(%d+):(%d+):")
    if path and line and col then
      jump_to_file(path, tonumber(line), tonumber(col))
      return true
    end
  end

  local items = {}
  for _, match in ipairs(matches) do
    local path, line, col, text = match:match("^(.-):(%d+):(%d+):(.*)$")
    if path and line and col then
      table.insert(items, {
        filename = path,
        lnum = tonumber(line),
        col = tonumber(col),
        text = vim.trim(text),
      })
    end
  end

  if #items > 0 then
    vim.fn.setqflist({}, " ", { title = "Blade class definitions", items = items })
    vim.cmd.copen()
    return true
  end

  vim.notify("Definition not found", vim.log.levels.INFO)
  return false
end

function M.goto_definition(bufnr)
  local filetype = vim.bo[bufnr].filetype

  if filetype == "blade" and not has_definition_client(bufnr) then
    M.search_blade_class_definition(bufnr)
    return
  end

  vim.lsp.buf_request_all(bufnr, definition_method, vim.lsp.util.make_position_params(), function(results)
    if jump_to_locations(results) then
      return
    end

    if filetype == "blade" then
      M.search_blade_class_definition(bufnr)
      return
    end

    vim.notify("Definition not found", vim.log.levels.INFO)
  end)
end

function M.setup_blade_keymaps(bufnr)
  vim.keymap.set("n", "gd", function()
    M.goto_definition(bufnr)
  end, {
    buffer = bufnr,
    desc = "Blade go to definition or search class",
  })
end

function M.on_attach(_, bufnr)
  local function opts(desc)
    return { buffer = bufnr, desc = "LSP " .. desc }
  end

  vim.keymap.set("n", "gd", function()
    M.goto_definition(bufnr)
  end, opts(vim.bo[bufnr].filetype == "blade"
    and "Go to definition or search class"
    or "Go to definition"))
  vim.keymap.set("n", "gr", vim.lsp.buf.references, opts("List references"))
  vim.keymap.set("n", "gi", vim.lsp.buf.implementation, opts("Go to implementation"))
  vim.keymap.set("n", "K", vim.lsp.buf.hover, opts("Hover doc"))
  vim.keymap.set("n", "<leader>ca", vim.lsp.buf.code_action, opts("Code action"))
end

function M.on_init(client)
  local is_rust_analyzer = client.name == "rust-analyzer" or client.name == "rust_analyzer"

  if not is_rust_analyzer and client:supports_method(semantic_tokens_method) then
    client.server_capabilities.semanticTokensProvider = nil
  end
end

function M.capabilities()
  local capabilities = vim.lsp.protocol.make_client_capabilities()
  local ok, cmp_nvim_lsp = pcall(require, "cmp_nvim_lsp")

  if ok then
    capabilities = cmp_nvim_lsp.default_capabilities(capabilities)
  end

  return capabilities
end

function M.default_config()
  return {
    on_attach = M.on_attach,
    on_init = M.on_init,
    capabilities = M.capabilities(),
  }
end

function M.extend(config)
  return vim.tbl_deep_extend("force", M.default_config(), config or {})
end

function M.enable_inlay_hints(client, bufnr)
  if client:supports_method(inlay_hint_method) then
    vim.lsp.inlay_hint.enable(true, { bufnr = bufnr })
  end
end

return M
