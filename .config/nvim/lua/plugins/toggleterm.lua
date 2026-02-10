return {
  'akinsho/toggleterm.nvim',
  version = "*",
  config = function()
    require("toggleterm").setup({
      size = 20,
      open_mapping = [[<c-\>]],  -- Ctrl-\ でトグル
      hide_numbers = true,
      shade_terminals = true,
      start_in_insert = true,
      insert_mappings = true,
      terminal_mappings = true,
      persist_size = true,
      direction = 'float',  -- 'horizontal', 'vertical', 'tab', 'float'
      close_on_exit = true,
      shell = vim.o.shell,
      float_opts = {
        border = 'curved',
        winblend = 0,
        highlights = {
          border = "Normal",
          background = "Normal",
        },
      },
    })
    
    -- キーマップ
    local opts = { noremap = true, silent = true }
    
    -- Ctrl-\ でフローティングターミナルをトグル
    vim.keymap.set('n', '<C-\\>', '<cmd>ToggleTerm<CR>', opts)
    vim.keymap.set('t', '<C-\\>', '<cmd>ToggleTerm<CR>', opts)
    
    -- 水平分割ターミナル
    vim.keymap.set('n', '<leader>th', '<cmd>ToggleTerm direction=horizontal<CR>', opts)
    
    -- 垂直分割ターミナル
    vim.keymap.set('n', '<leader>tv', '<cmd>ToggleTerm direction=vertical<CR>', opts)
    
    -- フローティングターミナル
    vim.keymap.set('n', '<leader>tf', '<cmd>ToggleTerm direction=float<CR>', opts)
    
    -- Escでターミナルモードから抜ける
    vim.keymap.set('t', '<Esc>', '<C-\\><C-n>', opts)
  end,
}
