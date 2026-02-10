local map = vim.api.nvim_set_keymap

-- Insert mode escape
vim.keymap.set("i", "jj", "<esc>")
vim.keymap.set("i", "kk", "<esc>")
vim.keymap.set("i", "jk", "<esc>")
vim.keymap.set("i", "kj", "<esc>")

-- move window
map('n', '<Leader>j', '<C-w>j', { noremap = true, silent = true })
map('n', '<Leader>k', '<C-w>k', { noremap = true, silent = true })
map('n', '<Leader>l', '<C-w>l', { noremap = true, silent = true })
map('n', '<Leader>h', '<C-w>h', { noremap = true, silent = true })

-- split window
map('n', '<Leader>s', ':sp<CR>', { noremap = true })
map('n', '<Leader>v', ':vs<CR>', { noremap = true })

-- close window
map('n', '<Leader>w', ':w<CR>', { noremap = true })
map('n', '<Leader>q', ':q<CR>', { noremap = true })
map('n', '<Leader>wq', ':wq<CR>', { noremap = true })

-- open terminal
map('n', '<Leader>tt', ':terminal<CR>', { noremap = true })
map('n', '<Leader>tv', ':vsplit | terminal<CR>', { noremap = true })
map('n', '<Leader>ts', ':split | terminal<CR>', { noremap = true })

-- tab
map('n', 'gl', 'gt', { noremap = true })
map('n', 'gh', 'gT', { noremap = true })
map('n', 'gk', ':tabnew<CR>', { noremap = true })
map('n', 'gj', ':tabclose<CR>', { noremap = true })
map('n', 'gJ', ':tabclose!<CR>', { noremap = true })

-- move in insert
map('i', '<C-k>', '<Up>', {})
map('i', '<C-j>', '<Down>', {})
map('i', '<C-h>', '<Left>', {})
map('i', '<C-l>', '<Right>', {})

-- show diagnostics
map('n', '<Leader>d', ':lua vim.diagnostic.open_float()<CR>', { noremap = true })

-- toggle comment
map('n', '<C-_>', 'gcc', { noremap = false })
map('v', '<C-_>', 'gc', { noremap = false })

-- redo
map('n', 'U', '<C-r>', { noremap = false })
