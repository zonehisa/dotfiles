vim.o.encoding = 'utf-8'
vim.o.number = true
vim.o.relativenumber = true

-- ノーマル/ビジュアルモードでは相対行番号
vim.api.nvim_create_autocmd({"InsertLeave", "BufEnter"}, {
  callback = function()
    vim.opt.relativenumber = true
  end,
})

-- インサートモードでは絶対行番号
vim.api.nvim_create_autocmd("InsertEnter", {
  callback = function()
    vim.opt.relativenumber = false
  end,
})

vim.o.smartindent = true
if vim.fn.executable("pbcopy") == 1
  or vim.fn.executable("wl-copy") == 1
  or vim.fn.executable("xclip") == 1
  or vim.fn.executable("xsel") == 1 then
  vim.o.clipboard = "unnamedplus"
end
vim.o.list = true
vim.o.expandtab = true
vim.o.tabstop = 2
vim.o.shiftwidth = 2
vim.o.wrap = false
vim.o.termguicolors = true
vim.o.wildmenu = true
vim.o.ruler = true
vim.o.smartcase = true
vim.o.showmatch = true

vim.g.mapleader = ' '
vim.g.maplocalleader = "\\"
